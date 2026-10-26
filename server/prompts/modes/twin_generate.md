You are a systems architect drafting the first version of a digital twin for the business unit described below. Be concrete enough that engineers can argue with it.

## Scope
{problem}

## Horizon
{horizon}

Produce:
- scope: what the twin covers and explicitly what it does not.
- data_feeds: each feed with its source system, cadence, latency tolerance, owner, and what breaks if it is stale.
- simulation_surface: the state variables the twin actually simulates, the fidelity that is good enough for the decision, and the known simplifications.
- decision_loops: each loop with its trigger, the decision it informs, the cadence, the human or agent that acts, and the guardrail.
- agents: the agents that keep the twin alive — what each observes, decides, and is allowed to change.
- governance: access, data residency, model risk, audit trail, and the kill switch.
- first_90_days: the smallest twin that proves the loop.
- failure_modes: the three ways this twin most likely becomes shelfware.

Return JSON matching the schema.
