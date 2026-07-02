"""Work Chart v2 JSON schemas: agent-era taxonomy for process steps."""

AGENT_FUNCTIONS = [
    "retrieval",
    "reasoning",
    "generation",
    "orchestration",
    "extraction",
    "validation",
    "communication",
]


def _steps_schema(owners):
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "step": {"type": "string"},
                "task": {"type": "string"},
                "owner": {"type": "string", "enum": owners},
                "agentFunction": {"type": ["string", "null"], "enum": AGENT_FUNCTIONS + [None]},
                "reusableAgentAsset": {
                    "type": ["object", "null"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "reusePotential": {"type": "string", "enum": ["single", "team", "org"]},
                    },
                    "required": ["name", "description", "reusePotential"],
                    "additionalProperties": False,
                },
                "successTarget": {"type": "string"},
                "rule": {"type": "string"},
                "estimatedTimeMinutes": {"type": "number"},
                "estimatedCostUSD": {"type": "number"},
                "fteFraction": {"type": "number"},
                "compute": {
                    "type": ["object", "null"],
                    "properties": {
                        "modelSize": {"type": "string", "enum": ["S", "M", "L", "XL"]},
                        "estimatedInputTokens": {"type": "number"},
                        "estimatedOutputTokens": {"type": "number"},
                        "tools": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["modelSize", "estimatedInputTokens", "estimatedOutputTokens", "tools"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "step",
                "task",
                "owner",
                "agentFunction",
                "reusableAgentAsset",
                "successTarget",
                "rule",
                "estimatedTimeMinutes",
                "estimatedCostUSD",
                "fteFraction",
                "compute",
            ],
            "additionalProperties": False,
        },
    }


def _process_schema(owners):
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "steps": _steps_schema(owners),
            "assumptions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "steps", "assumptions"],
        "additionalProperties": False,
    }


CURRENT_OWNERS = ["Human"]
FUTURE_OWNERS = ["Human", "AI Agent", "Hybrid", "Digital Twin"]

DELTAS_SCHEMA = {
    "type": "object",
    "properties": {
        "timeSavedPct": {"type": "number"},
        "costSavedPct": {"type": "number"},
        "fteFreed": {"type": "number"},
        "narrative": {"type": "string"},
    },
    "required": ["timeSavedPct", "costSavedPct", "fteFreed", "narrative"],
    "additionalProperties": False,
}

AGENT_FACTORY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "assetName": {"type": "string"},
            "functionType": {"type": "string", "enum": AGENT_FUNCTIONS},
            "description": {"type": "string"},
            "usedInSteps": {"type": "array", "items": {"type": "string"}},
            "buildComplexity": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["assetName", "functionType", "description", "usedInSteps", "buildComplexity"],
        "additionalProperties": False,
    },
}

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "currentProcess": _process_schema(CURRENT_OWNERS),
        "futureProcess": _process_schema(FUTURE_OWNERS),
        "deltas": DELTAS_SCHEMA,
        "agentFactory": AGENT_FACTORY_SCHEMA,
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["id", "question", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["currentProcess", "futureProcess", "deltas", "agentFactory", "questions"],
    "additionalProperties": False,
}

REFINED_SCHEMA = {
    "type": "object",
    "properties": {
        "currentProcess": GENERATE_SCHEMA["properties"]["currentProcess"],
        "futureProcess": GENERATE_SCHEMA["properties"]["futureProcess"],
        "deltas": DELTAS_SCHEMA,
        "agentFactory": AGENT_FACTORY_SCHEMA,
    },
    "required": ["currentProcess", "futureProcess", "deltas", "agentFactory"],
    "additionalProperties": False,
}

REVISE_SCHEMA = {
    "type": "object",
    "properties": {
        "currentProcess": GENERATE_SCHEMA["properties"]["currentProcess"],
        "futureProcess": GENERATE_SCHEMA["properties"]["futureProcess"],
        "deltas": DELTAS_SCHEMA,
        "agentFactory": AGENT_FACTORY_SCHEMA,
        "changeLog": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stepRef": {"type": "string"},
                    "changeType": {"type": "string", "enum": ["added", "removed", "modified", "reassigned"]},
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["stepRef", "changeType", "before", "after", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["currentProcess", "futureProcess", "deltas", "agentFactory", "changeLog"],
    "additionalProperties": False,
}

BREAKTHROUGH_SCHEMA = {
    "type": "object",
    "properties": {
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "thesis": {"type": "string"},
                    "whatChanges": {"type": "string"},
                    "ambitionLevel": {
                        "type": "string",
                        "enum": ["incremental", "step-change", "reinvention"],
                    },
                    "orderOfMagnitudeImpact": {"type": "string"},
                    "prerequisites": {"type": "array", "items": {"type": "string"}},
                    "firstExperiment": {"type": "string"},
                },
                "required": [
                    "title",
                    "thesis",
                    "whatChanges",
                    "ambitionLevel",
                    "orderOfMagnitudeImpact",
                    "prerequisites",
                    "firstExperiment",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["opportunities"],
    "additionalProperties": False,
}
