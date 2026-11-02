"""Thread-safe Venice API client.

Wraps chat completions (structured + streaming + search-augmented), web scrape,
image generation, and model listing. All long operations honor retry/backoff on
transient failures.
"""
import json
import logging
import os
import random
import re
import time

import requests

from ..config import Config
from .errors import RetryableVeniceError, VeniceError

logger = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
CHAT_TIMEOUT = 90
LONG_TIMEOUT = 300


class Attempts:
    """Upstream requests left for one logical call, shared by HTTP retries and the JSON repair retry."""

    def __init__(self, left=MAX_ATTEMPTS):
        self.left = left


def _strip_json_fence(text):
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.I | re.S)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def _extract_json(text):
    """Parse model output as JSON.

    Accept a raw JSON value, a ```json fence, or prose around one object or array.
    """
    if not isinstance(text, str):
        raise VeniceError("Model returned non-string, non-JSON content")
    stripped = _strip_json_fence(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (stripped.find("{"), stripped.find("[")) if i != -1]
    if not starts:
        raise VeniceError(f"No JSON found in model output: {text[:200]!r}")
    start = min(starts)
    try:
        value, _end = json.JSONDecoder().raw_decode(stripped[start:])
    except json.JSONDecodeError as exc:
        raise VeniceError(f"Unbalanced JSON in model output: {exc}") from exc
    return value


class VeniceClient:
    def __init__(self, api_key=None, base_url=None, timeout=CHAT_TIMEOUT):
        self.api_key = api_key or os.environ.get("VENICE_API_KEY", "")
        self.timeout = timeout
        self.base_url = (base_url or Config.VENICE_BASE_URL).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    # ------------------------------------------------------------------ http
    def _request(self, method, path, *, json_body=None, timeout=None, stream=False, attempts=None):
        url = f"{self.base_url}{path}"
        attempts = attempts or Attempts()
        last_error = None
        while attempts.left > 0:
            attempts.left -= 1
            try:
                resp = self._session.request(
                    method, url, json=json_body, timeout=timeout or self.timeout, stream=stream
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = RetryableVeniceError(f"{type(exc).__name__} calling {path}")
            else:
                if resp.status_code < 400:
                    return resp
                body = resp.text[:2000]
                if resp.status_code in RETRY_STATUSES and attempts.left > 0:
                    retry_after = resp.headers.get("Retry-After")
                    last_error = RetryableVeniceError(
                        f"HTTP {resp.status_code} from {path}", resp.status_code, body
                    )
                    if retry_after:
                        try:
                            time.sleep(min(float(retry_after), 30))
                            continue
                        except ValueError:
                            pass
                else:
                    raise VeniceError(
                        f"HTTP {resp.status_code} from {path}: {body}",
                        resp.status_code,
                        body,
                    )
            if attempts.left > 0:
                time.sleep((2 ** (MAX_ATTEMPTS - attempts.left)) + random.random())
        raise last_error or VeniceError(f"Request to {path} failed")

    # ---------------------------------------------------------------- models
    def list_models(self, model_type=None):
        path = "/models"
        if model_type:
            path += f"?type={model_type}"
        resp = self._request("GET", path, timeout=30)
        return resp.json().get("data", [])

    # ------------------------------------------------------------- chat APIs
    def structured(
        self,
        model,
        messages,
        schema_name,
        schema,
        *,
        temperature=0.7,
        max_completion_tokens=6000,
        venice_params=None,
        ledger=None,
        stage=None,
    ):
        """Chat completion constrained to a JSON schema. Returns parsed dict.

        Thinking models can spend the whole completion budget on reasoning,
        leaving empty content once thinking is stripped — when that happens,
        retry once with thinking disabled and a larger budget. Retries included,
        one call makes at most MAX_ATTEMPTS upstream requests."""
        vp = {"strip_thinking_response": True, "include_venice_system_prompt": False}
        vp.update(venice_params or {})
        attempts = Attempts()

        def attempt(params, tokens, msgs):
            payload = {
                "model": model,
                "messages": msgs,
                "temperature": temperature,
                "max_completion_tokens": tokens,
                "response_format": {"type": "json_object"},
                "venice_parameters": params,
            }
            resp = self._request("POST", "/chat/completions", json_body=payload, attempts=attempts)
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise VeniceError(f"No choices in response from {model}")
            message = choices[0].get("message", {})
            content = message.get("content")
            # Thinking models sometimes leave `content` empty and put the actual
            # answer (or JSON after a <think> block) in `reasoning_content`.
            if not (content or "").strip():
                content = message.get("reasoning_content") or ""
            parsed = _extract_json(content)
            if ledger is not None:
                ledger.record(stage or schema_name, model, data.get("usage", {}))
            return parsed

        guided = list(messages)
        if schema:
            guided = [
                {
                    "role": "system",
                    "content": "Return one JSON value matching this schema. No markdown.\n"
                    + json.dumps(schema),
                }
            ] + guided
        try:
            return attempt(vp, max_completion_tokens, guided)
        except (VeniceError, json.JSONDecodeError) as exc:
            if (isinstance(exc, VeniceError) and exc.status is not None) or attempts.left <= 0:
                raise
            logger.warning("Structured output from %s was not valid JSON (%s); retrying once", model, exc)
            repair = guided + [
                {
                    "role": "user",
                    "content": f"Return valid JSON only. Parse error: {exc}",
                }
            ]
            # Empty or cut-off output usually means reasoning used the budget: retry without thinking.
            return attempt({**vp, "disable_thinking": True}, max(max_completion_tokens * 2, 4000), repair)

    def chat_search(
        self,
        model,
        messages,
        *,
        web="on",
        citations=True,
        x_search=False,
        scraping=False,
        temperature=0.6,
        max_completion_tokens=4000,
        ledger=None,
        stage=None,
    ):
        """Search-augmented chat completion. Returns content + citations +
        raw search results provided by Venice."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "venice_parameters": {
                "strip_thinking_response": True,
                "include_venice_system_prompt": False,
                "enable_web_search": web,
                "enable_web_citations": citations,
                "return_search_results_as_documents": True,
                "enable_x_search": bool(x_search),
                "enable_web_scraping": bool(scraping),
            },
        }
        resp = self._request("POST", "/chat/completions", json_body=payload)
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise VeniceError(f"No choices in search response from {model}")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        search_results = self._collect_search_results(data, message)
        if ledger is not None:
            ledger.record(stage or "search", model, data.get("usage", {}))
        return {"content": content, "search_results": search_results}

    @staticmethod
    def _collect_search_results(data, message):
        """Venice has surfaced search results in a few shapes across versions;
        check the known locations."""
        results = []
        for container in (
            data.get("venice_parameters") or {},
            message,
            data,
        ):
            found = container.get("web_search_citations") or container.get("search_results")
            if isinstance(found, list):
                results.extend(found)
        deduped, seen = [], set()
        for r in results:
            key = r.get("url") if isinstance(r, dict) else str(r)
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped

    def chat_stream(
        self,
        model,
        messages,
        *,
        temperature=0.6,
        max_completion_tokens=8000,
        venice_params=None,
        on_usage=None,
    ):
        """Yield content deltas from a streaming chat completion."""
        vp = {"strip_thinking_response": True, "include_venice_system_prompt": False}
        vp.update(venice_params or {})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "venice_parameters": vp,
        }
        resp = self._request("POST", "/chat/completions", json_body=payload, stream=True)
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            chunk = raw_line[len("data:") :].strip()
            if chunk == "[DONE]":
                break
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if event.get("usage") and on_usage:
                on_usage(event["usage"])
            for choice in event.get("choices", []):
                delta = choice.get("delta", {}).get("content")
                if delta:
                    yield delta

    # ------------------------------------------------------------ web scrape
    def scrape(self, url):
        resp = self._request("POST", "/web/scrape", json_body={"url": url}, timeout=120)
        return resp.json()

    # ------------------------------------------------------------------ image
    def generate_image(self, prompt, *, model=None, aspect_ratio="1:1", style_preset=None):
        """Generate an image. Newer Venice image models take aspect_ratio;
        older ones still want width/height — try the new shape first and fall
        back on the specific 400 that asks for the other."""
        base = {
            "model": model or Config.MODEL_ROLE_DEFAULTS["image"],
            "prompt": prompt,
            "format": "webp",
            "safe_mode": True,
        }
        if style_preset:
            base["style_preset"] = style_preset
        attempts = Attempts()
        try:
            resp = self._request(
                "POST", "/image/generate",
                json_body={**base, "aspect_ratio": aspect_ratio}, timeout=LONG_TIMEOUT, attempts=attempts,
            )
        except VeniceError as exc:
            if exc.status != 400 or "aspect_ratio" not in (exc.body or ""):
                raise
            ratios = {"1:1": (1024, 1024), "4:3": (1024, 768), "16:9": (1280, 720), "9:16": (720, 1280)}
            width, height = ratios.get(aspect_ratio, (1024, 1024))
            if attempts.left <= 0:
                raise
            resp = self._request(
                "POST", "/image/generate",
                json_body={**base, "width": width, "height": height}, timeout=LONG_TIMEOUT, attempts=attempts,
            )
        return resp.json()


_default_client = None


def get_client():
    global _default_client
    if _default_client is None:
        _default_client = VeniceClient()
    return _default_client
