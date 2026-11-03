---
name: read-top5
description: Read the judge's Top 5 from an AI Partner job state and say what is still missing.
---

# Read the Top 5

Use this after `run-engagement` when the user wants the five moves, not a new job.

1. Use the saved job state. Do not start a second job to answer this.
2. Read `state.top5` when it is present. Otherwise read the panel consensus, dissent, and the now / next / later lists in `state.panel`.
3. Show each move with its title and the reason in the state. If a field is absent, say it is not in the state yet.
4. Do not invent customers, quotes, or numbers that are not in the state or its citations.
