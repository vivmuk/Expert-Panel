# Work Chart Application: Methodology & Recreation Guide

This document outlines the complete methodology, prompts, and technical architecture used to recreate the **Work Chart** application.

## 1. Methodology Overview

The **Work Chart** is a single-page web application designed to help users visualize and optimize business workflows by comparing a "Current (Human-Only)" process with a "Future (AI-Assisted)" process.

### Core Philosophy
1.  **Baseline vs. Optimized**: Always establish a human-only baseline to calculate realistic ROI (time/cost savings).
2.  **Human-in-the-Loop**: Tasks are classified into three ownership types:
    *   **Human**: Requires judgment, physical presence, or high creativity.
    *   **Agent**: Fully automatable by AI.
    *   **Hybrid**: AI-assisted but human-supervised.
3.  **Iterative Refinement**: The AI identifies ambiguities and asks clarifying questions to improve the chart's accuracy.

## 2. Technical Architecture

*   **Stack**: Vanilla HTML5, JavaScript (ES6+), Tailwind CSS (via CDN).
*   **AI Provider**: [Venice.ai](https://venice.ai/) API (compatible with OpenAI-style chat completions).
*   **Models**:
    *   Primary: `llama-3.3-70b` (default for logic/analysis).
    *   Fast/Tooling: `mistral-31-24b` or `llama-3.2-3b` (used for autofill/simple tasks).
    *   Fallback: Hardcoded list if API model fetch fails.
*   **PDF Generation**: Client-side rendering using `html2canvas` and `jspdf`.

## 3. Prompts & Workflow

The application follows a two-stage generation process.

### Stage 1: Initial Chart Generation

**Goal**: Analyze the user's raw input and generate a baseline comparison + clarifying questions.

#### System Prompt
```text
You are an expert business process analyst. Based on the workflow description, produce BOTH the current human-only process and a future AI-assisted process.
Rules:
- The current process must assign owner = "Human" for every step.
- The future process can use owner = "Human", "Agent", or "Hybrid".
- For every step, estimate time in minutes. Do NOT include human labor cost.
- For Agent or Hybrid steps, include a compute object: { "modelId": string, "estimatedInputTokens": number, "estimatedOutputTokens": number, "notes": string, "tools": ["list of tools/capabilities needed"] }.
- Keep step lists aligned where possible so comparisons are clear.
- Ask enough clarifying questions to resolve ambiguities (no hard limit; include as many as needed).
Return ONLY JSON with this exact structure:
{
  "currentProcess": {"name": "string", "steps": [{"step": "string", "task": "string", "owner": "Human", "successTarget": "string", "rule": "string", "estimatedTimeMinutes": number}], "assumptions": ["string"]},
  "futureProcess": {"name": "string", "steps": [{"step": "string", "task": "string", "owner": "Human|Agent|Hybrid", "successTarget": "string", "rule": "string", "estimatedTimeMinutes": number, "compute": {"modelId": "string", "estimatedInputTokens": number, "estimatedOutputTokens": number, "notes": "string", "tools": ["string"]}}], "assumptions": ["string"]},
  "questions": ["string"]
}
```

#### User Prompt
```text
Workflow description: "{USER_INPUT}"
```

---

### Stage 2: Refinement (Q&A)

**Goal**: Update the charts based on the user's answers to the clarifying questions.

#### System Prompt
```text
You are an expert business process analyst. Refine BOTH the current human-only process and the future AI-assisted process using the user's answers.
Constraints:
- Current process must keep owner = "Human" for all steps.
- Estimate time (minutes) for each step. Do NOT include human labor cost.
- For Agent or Hybrid steps, include/adjust the compute object: { modelId, estimatedInputTokens, estimatedOutputTokens, notes, tools: ["list of tools/capabilities needed"] }.
Return ONLY JSON of the form:
{
  "currentProcess": ...,
  "futureProcess": ...
}
```

#### User Prompt
```text
Original Workflow: "{USER_INPUT}"

Initial Comparison (for context):
{JSON_DUMP_OF_INITIAL_CHART}

User's Answers:
- Q: {QUESTION_1}
  A: {ANSWER_1}
...
```

---

### Helper: Auto-Fill Answers

**Goal**: Use a smaller/faster model to draft answers for the user if they're stuck.

#### System Prompt
```text
You are assisting with workflow clarification. For the given original workflow and the initial work chart steps, draft concise, practical first-pass answers to each question. Keep each answer to one sentence, be specific, and assume reasonable defaults if unspecified.
```

#### User Prompt
```text
Original Workflow: "{USER_INPUT}"

Initial Steps (for context):
{JSON_DUMP_OF_INITIAL_STEPS}

Questions to answer:
1. {QUESTION_1}
...

Return ONLY a JSON object of the form:
{"answers": ["answer 1", "answer 2", ...]}
```

## 4. Data Models (JSON Schemas)

The app enforces structure using these schemas (implicit in the prompts and explicit in the JS validation code).

### Process Step Object
```json
{
  "step": "Step Name",
  "task": "Detailed description of the task",
  "owner": "Human" | "Agent" | "Hybrid",
  "successTarget": "Criteria for success (e.g., 'Response sent within 5 mins')",
  "rule": "Business rule (e.g., 'If > $500, requires approval')",
  "estimatedTimeMinutes": 15,
  "compute": {  // Only for Agent/Hybrid
    "modelId": "llama-3.3-70b",
    "estimatedInputTokens": 150,
    "estimatedOutputTokens": 300,
    "notes": "Reasoning for model choice",
    "tools": ["web_search", "code_interpreter"]
  }
}
```

### Full Comparison Object
```json
{
  "currentProcess": {
    "name": "Manual Workflow",
    "steps": [...],
    "assumptions": ["Assumption 1", ...]
  },
  "futureProcess": {
    "name": "AI-Augmented Workflow",
    "steps": [...],
    "assumptions": ["Assumption 1", ...]
  }
}
```
