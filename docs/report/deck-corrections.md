# Deck corrections for a later file

Do not edit `server/static/deck/index.html` or anything else under `server/static/deck/`. That file is the FIRST 1000 original. It has 14 `<section class="slide">` blocks. `server/static/deck/README.md` says ten slides. A correction belongs in a new file. Keep paper and cobalt `#0033CC`. Show `/chat` and `/connect`, say the first engagement is free, and leave out prices and email addresses.

| # | id | Correction to carry into the new file |
|---|---|---|
| 1 | `s1` | "Describe a problem in Slack or Telegram." The public page is `/chat`. Slack and Telegram are not marked Live. |
| 2 | `s2` | Slack, email, and CRM are the customer's tools in the problem statement. They are not AI Partner channels. |
| 3 | `s3` | "Live web and X research" matches the panel runner. `/chat` research in this repo is the Exa search path. An X search on `/chat` is not what this run observed. |
| 4 | `s4` | The walkthrough is labeled illustrative and still says Slack, "Pre-run estimate is under $2", and "Saved as rev 2." The `$2` confirm is `COST_CONFIRM_THRESHOLD = 2.0` in the React launcher. `/chat` has no dollar estimate. SQLite revisions belong to `POST /api/runs`, not to the public chat slot. |
| 5 | `s5` | Maritime demo from public docs. Keep the demo label. |
| 6 | `s6` | "Live in the team's Slack" is a proposed workflow. |
| 7 | `s7` | Illustrative estimate. Keep the label. |
| 8 | `s8` | "Every engagement keeps its revision history" is the SQLite runner. Public chat history is one browser slot. "Telegram or Slack in" and "confirm over $2, auto-stop at 3×" describe `POST /api/runs`, not `/chat`. |
| 9 | `scomp` | Keiki is marked Next, and the embedded JSON says no Keiki agent is live. Both hosts' `/chat` pages mark iMessage and Email Live. That live mark was not re-proved by sending a message. Supermemory is marked Next. The write path is in the repo. Whether the host has the API key is unknown. |
| 10 | `sres` | Status date on the slide is Nov 2, 2026. Keiki is "Account · next." Keep this table in the original. Put a later status only in the new file. |
| 11 | `s9` | "Slack, Telegram, the CRM, the shared drive" as installed agents. Those channels are not marked Live. |
| 12 | `s10` | Proposed sprint and retainer prices, and a claim that model cost is estimated before the free engagement. Omit this slide from the corrected file. |
| 13 | `s11` | "9 engagement modes" matches `GET /api/modes`. "100 expert personas" is the panel runner cap. `/chat` seats 20. The "~192" viv-skills count is outside this repo and was not counted. |
| 14 | `s12` | The three `/chat` links and "First engagement free, no key needed" match the public page. Keep this. |

No website copy was changed in the hardening PR. The Connect page still says push mode for a customer's own account is coming soon. The operator route `POST /keiki/turn` exists in the repo. Those are different claims, and this PR does not rewrite the page.
