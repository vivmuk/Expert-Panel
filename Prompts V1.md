# Prompts V1 - Expert Panel & Work Chart

**Version:** 1.0  
**Last Updated:** October 7, 2025  
**Applications:** Expert Panel (app.py) & Work Chart (Work Chart.html)

---

## Table of Contents

1. [Expert Panel App Prompts](#expert-panel-app-prompts)
   - [1.1 Persona Generation](#11-persona-generation)
   - [1.2 Expert Insight Generation](#12-expert-insight-generation)
   - [1.3 Fallback Market Intelligence](#13-fallback-market-intelligence)
   - [1.4 Synthesis Report Generation](#14-synthesis-report-generation)
2. [Work Chart App Prompts](#work-chart-app-prompts)
   - [2.1 Initial Workflow Chart Generation](#21-initial-workflow-chart-generation)
   - [2.2 Chart Refinement](#22-chart-refinement)
   - [2.3 Question Auto-fill](#23-question-auto-fill)

---

## Expert Panel App Prompts

### 1.1 Persona Generation

**Model Used:** `qwen3-235b` (Venice Large 1.1)  
**Runs:** 1x per analysis  
**Purpose:** Generate 15 diverse expert personas for analyzing a business problem

**System/User Prompt:**

```
Given the business problem: "{business_problem}"

Identify and define exactly 15 diverse expert personas that could offer unique and valuable insights.

IMPORTANT GUIDELINES:
- NO quantum computing, quantum physics, or quantum technology experts
- Focus on the widest breadth of relevant expertise
- Include traditional business disciplines (strategy, finance, operations, marketing, HR, legal)
- Include industry-specific experts relevant to the problem domain
- Include technology and digital transformation experts
- Include customer experience and behavioral experts
- Include risk management and compliance experts
- Include innovation and R&D experts
- Include sustainability and ESG experts
- Include international/global market experts
- Include data analytics and AI/ML experts (non-quantum)
- Include supply chain and logistics experts
- Include regulatory and policy experts

Each expert should have distinct expertise that doesn't significantly overlap with others.
Ensure the experts collectively cover all major aspects that could impact the business problem.

Your response MUST be a JSON object adhering to the specified schema. 
The JSON should contain a single key "personas", which is an array of 15 persona objects.
Each persona object must have 'name' (string), 'description' (string), and 'focus_areas' (array of strings).
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "personas": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "description": {"type": "string"},
          "focus_areas": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["name", "description", "focus_areas"]
      }
    }
  },
  "required": ["personas"]
}
```

---

### 1.2 Expert Insight Generation

**Model Used:** `qwen3-next-80b` (Qwen 3 Next 80B - 262K context)  
**Runs:** 15x per analysis (once per expert)  
**Purpose:** Generate detailed insights from each expert persona's unique perspective

**System/User Prompt:**

```
You are '{persona_name}'. Your expertise: {persona_description}. Focus: {persona_focus_areas}.
Analyze the business problem: "{business_problem}" strictly from your unique perspective as '{persona_name}'.

Your response MUST be a JSON object adhering to the specified schema.
The JSON should contain 'persona_name' (string, matching "{persona_name}") and 'insights_and_analysis' (array of objects).
Each item in 'insights_and_analysis' must have:
- 'insight' (string): Your key insight or recommendation
- 'supporting_reasoning' (string): Detailed reasoning for your insight
- 'confidence_level' (enum: "High", "Medium", "Low"): Your confidence in this insight
- 'implementation_ideas' (array of 3 strings): Three specific, actionable ideas on how to accomplish this insight
- Optionally 'identified_risks' (array of strings) and 'identified_opportunities' (array of strings)

For each insight, provide exactly 3 implementation ideas that are specific, actionable, and practical.
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "persona_name": {"type": "string"},
    "insights_and_analysis": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "insight": {"type": "string"},
          "supporting_reasoning": {"type": "string"},
          "confidence_level": {"type": "string", "enum": ["High", "Medium", "Low"]},
          "implementation_ideas": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3
          },
          "identified_risks": {"type": "array", "items": {"type": "string"}},
          "identified_opportunities": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["insight", "supporting_reasoning", "confidence_level", "implementation_ideas"]
      }
    }
  },
  "required": ["persona_name", "insights_and_analysis"]
}
```

---

### 1.3 Fallback Market Intelligence

**Model Used:** `qwen-2.5-qwq-32b`  
**Runs:** 5x per analysis (one per intelligence type)  
**Purpose:** Generate market intelligence when web search is unavailable

#### 1.3.1 Market Size Analysis

**Prompt:**

```
Based on current market knowledge, provide analysis of market size and growth for: {business_problem}

Include:
- Estimated market size and growth trends
- Key market segments and their characteristics
- Geographic distribution and expansion opportunities
- Revenue models and monetization approaches
- Market maturity indicators
```

#### 1.3.2 Current Solutions Analysis

**Prompt:**

```
Based on current knowledge, describe existing solutions and approaches for: {business_problem}

Include:
- Common solution approaches and methodologies
- Technology stacks and tools typically used
- Implementation strategies and best practices
- Success factors and common challenges
- Market leaders and their approaches
```

#### 1.3.3 AI Applications Analysis

**Prompt:**

```
Based on current AI/ML knowledge, describe how AI technologies can be applied to: {business_problem}

Include:
- AI/ML use cases and applications
- Automation opportunities and implementations
- Data analytics and predictive modeling approaches
- Emerging technology integrations
- AI-powered tools and platforms
```

#### 1.3.4 Competitive Landscape Analysis

**Prompt:**

```
Based on current market knowledge, analyze the competitive landscape for: {business_problem}

Include:
- Key players and market leaders
- Competitive positioning and differentiation
- Market share distribution
- Strategic partnerships and acquisitions
- Innovation capabilities and technology stack
```

#### 1.3.5 Future Trends Analysis

**Prompt:**

```
Based on current trends and predictions, describe future opportunities for: {business_problem}

Include:
- Emerging market trends and opportunities
- Technology disruption and innovation
- Regulatory changes and compliance
- New business models and revenue streams
- Investment and funding trends
```

---

### 1.4 Synthesis Report Generation

**Model Used:** `qwen3-next-80b` (Qwen 3 Next 80B - 262K context)  
**Runs:** 1x per analysis  
**Purpose:** Synthesize all expert insights and market intelligence into actionable recommendations

**System/User Prompt:**

```
You are a Chief Synthesis Officer. Your task is to analyze the provided original business problem and a collection of insights from various expert personas.
Based on all this information, generate a concise and actionable synthesis report.

{insights_context}

Your response MUST be a JSON object adhering to the specified schema. The report should include:
1.  `cohesive_summary`: A brief overall summary of the situation and key findings (2-3 sentences).
2.  `key_themes`: A list of 2-4 dominant themes or patterns that emerged from the expert analyses.
3.  `potential_blind_spots`: A list of 1-3 areas that might have been overlooked, have conflicting opinions, or carry notable uncertainty/low confidence across personas.
4.  `actionable_next_steps`: A list of 3-5 concrete, actionable next steps to address the business problem. Each step should include:
    *   `step_description` (string): What needs to be done.
    *   `priority` (string enum: "High", "Medium", "Low").
    *   `suggested_rationale` (string, optional): Brief reason why this step is important based on the insights.
```

**Context Format (`insights_context`):**

```
Original Business Problem: {original_problem}

--- Collected Expert Insights ---

**Expert: {persona_name}** (Role: {definition})
  - Insight 1: {insight}
    Reasoning: {supporting_reasoning}
    Confidence: {confidence_level}
    Risks: {identified_risks}
    Opportunities: {identified_opportunities}

--- Market Intelligence & Real-Time Analysis ---

**{intel_title}**
  Confidence: {confidence_level}
  • {key_insight_1}
  • {key_insight_2}
  Full Content: {content}...

---
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "cohesive_summary": {"type": "string"},
    "key_themes": {"type": "array", "items": {"type": "string"}},
    "potential_blind_spots": {"type": "array", "items": {"type": "string"}},
    "actionable_next_steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_description": {"type": "string"},
          "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
          "suggested_rationale": {"type": ["string", "null"]}
        },
        "required": ["step_description", "priority"]
      }
    }
  },
  "required": ["cohesive_summary", "key_themes", "potential_blind_spots", "actionable_next_steps"]
}
```

---

## Work Chart App Prompts

### 2.1 Initial Workflow Chart Generation

**Model Used:** `qwen3-next-80b` (Qwen 3 Next 80B - 262K context) or user-selected model  
**Runs:** 1x per workflow generation  
**Purpose:** Generate both current (human-only) and future (AI-assisted) process workflows

**System Prompt:**

```
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

**User Prompt:**

```
Workflow description: "{user_input}"
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "currentProcess": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "step": {"type": "string"},
              "task": {"type": "string"},
              "owner": {"type": "string", "enum": ["Human"]},
              "successTarget": {"type": "string"},
              "rule": {"type": "string"},
              "estimatedTimeMinutes": {"type": "number"}
            },
            "required": ["step", "task", "owner", "successTarget", "rule", "estimatedTimeMinutes"]
          }
        },
        "assumptions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["steps"]
    },
    "futureProcess": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "step": {"type": "string"},
              "task": {"type": "string"},
              "owner": {"type": "string", "enum": ["Human", "Agent", "Hybrid"]},
              "successTarget": {"type": "string"},
              "rule": {"type": "string"},
              "estimatedTimeMinutes": {"type": "number"},
              "compute": {
                "type": "object",
                "properties": {
                  "modelId": {"type": "string"},
                  "estimatedInputTokens": {"type": "number"},
                  "estimatedOutputTokens": {"type": "number"},
                  "notes": {"type": "string"},
                  "tools": {"type": "array", "items": {"type": "string"}}
                }
              }
            },
            "required": ["step", "task", "owner", "successTarget", "rule", "estimatedTimeMinutes"]
          }
        },
        "assumptions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["steps"]
    },
    "questions": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["currentProcess", "futureProcess", "questions"]
}
```

---

### 2.2 Chart Refinement

**Model Used:** User-selected model (default: `qwen3-next-80b`)  
**Runs:** 1x per refinement request  
**Purpose:** Refine both current and future workflows based on user's answers to clarifying questions

**System Prompt:**

```
You are an expert business process analyst. Refine BOTH the current human-only process and the future AI-assisted process using the user's answers.
Constraints:
- Current process must keep owner = "Human" for all steps.
- Estimate time (minutes) for each step. Do NOT include human labor cost.
- For Agent or Hybrid steps, include/adjust the compute object: { modelId, estimatedInputTokens, estimatedOutputTokens, notes, tools: ["list of tools/capabilities needed"] }.
Return ONLY JSON of the form:
{
  "currentProcess": {"name": "string", "steps": [{"step": "string", "task": "string", "owner": "Human", "successTarget": "string", "rule": "string", "estimatedTimeMinutes": number}], "assumptions": ["string"]},
  "futureProcess": {"name": "string", "steps": [{"step": "string", "task": "string", "owner": "Human|Agent|Hybrid", "successTarget": "string", "rule": "string", "estimatedTimeMinutes": number, "compute": {"modelId": "string", "estimatedInputTokens": number, "estimatedOutputTokens": number, "notes": "string", "tools": ["string"]}}], "assumptions": ["string"]}
}
```

**User Prompt:**

```
Original Workflow: "{workflow_description}"

Initial Comparison (for context):
{JSON.stringify(initialComparison, null, 2)}
                
User's Answers:
- Q: {question_1}
  A: {answer_1}
- Q: {question_2}
  A: {answer_2}
...
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "currentProcess": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "step": {"type": "string"},
              "task": {"type": "string"},
              "owner": {"type": "string", "enum": ["Human"]},
              "successTarget": {"type": "string"},
              "rule": {"type": "string"},
              "estimatedTimeMinutes": {"type": "number"}
            },
            "required": ["step", "task", "owner", "successTarget", "rule", "estimatedTimeMinutes"]
          }
        },
        "assumptions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["steps"]
    },
    "futureProcess": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "step": {"type": "string"},
              "task": {"type": "string"},
              "owner": {"type": "string", "enum": ["Human", "Agent", "Hybrid"]},
              "successTarget": {"type": "string"},
              "rule": {"type": "string"},
              "estimatedTimeMinutes": {"type": "number"},
              "compute": {
                "type": "object",
                "properties": {
                  "modelId": {"type": "string"},
                  "estimatedInputTokens": {"type": "number"},
                  "estimatedOutputTokens": {"type": "number"},
                  "notes": {"type": "string"},
                  "tools": {"type": "array", "items": {"type": "string"}}
                }
              }
            },
            "required": ["step", "task", "owner", "successTarget", "rule", "estimatedTimeMinutes"]
          }
        },
        "assumptions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["steps"]
    }
  },
  "required": ["currentProcess", "futureProcess"]
}
```

---

### 2.3 Question Auto-fill

**Model Used:** `mistral-31-24b` (Venice Medium)  
**Runs:** 1x per auto-fill request  
**Purpose:** Draft concise, practical answers to clarifying questions

**System Prompt:**

```
You are assisting with workflow clarification. For the given original workflow and the initial work chart steps, draft concise, practical first-pass answers to each question. Keep each answer to one sentence, be specific, and assume reasonable defaults if unspecified.
```

**User Prompt:**

```
Original Workflow: "{workflow_description}"

Initial Steps (for context):
{JSON.stringify(initialWorkChart, null, 2)}

Questions to answer:
1. {question_1}
2. {question_2}
3. {question_3}
...

Return ONLY a JSON object of the form:
{"answers": ["answer 1", "answer 2", ...]}
```

**Expected JSON Schema:**

```json
{
  "type": "object",
  "properties": {
    "answers": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["answers"]
}
```

---

## Prompt Design Principles

### Expert Panel App

1. **Structured JSON Output:** All prompts enforce strict JSON schema compliance for reliable parsing
2. **Role-Based Perspective:** Each expert persona maintains their unique viewpoint throughout analysis
3. **Comprehensive Coverage:** Prompts ensure coverage of insights, risks, opportunities, and implementation ideas
4. **Confidence Tracking:** Experts rate their confidence level to identify areas of uncertainty
5. **Synthesis Focus:** Final synthesis emphasizes actionable next steps with priority levels

### Work Chart App

1. **Dual-Process Generation:** Prompts always generate both current (human-only) and future (AI-assisted) workflows
2. **Owner Classification:** Clear distinction between Human, Agent, and Hybrid task ownership
3. **AI Capability Tracking:** Compute objects track model requirements, token estimates, and required tools
4. **Iterative Refinement:** Questions and answers flow enables progressive workflow refinement
5. **Time-Based Metrics:** Focus on time estimates rather than cost for clearer value communication

---

## Version History

- **V1.0** (October 7, 2025): Initial documentation of all prompts across both applications
  - Expert Panel: 4 main prompt categories (persona generation, insight generation, market intelligence, synthesis)
  - Work Chart: 3 main prompt categories (chart generation, refinement, auto-fill)
  - Added AI agent recommendation functionality with tools tracking

---

## Notes

- All prompts use Venice AI API (https://api.venice.ai/api/v1/chat/completions)
- JSON schema validation ensures consistent, parseable responses
- Model selection is configurable based on task complexity and context requirements
- Prompts are designed to be model-agnostic where possible for flexibility


