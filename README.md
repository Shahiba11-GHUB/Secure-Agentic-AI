# Secure Agentic AI — Shahiba's Security Module (Starter)

This starter implements the **security scenario and policy engine** only, designed to connect later to the team's search/planning algorithms.

## Contents
- `policy_engine.py` — independent policy checker; unknown actions are denied.
- `scenarios/suspicious_login.json` — initial synthetic investigation scenario with action costs, prerequisites, effects, and policies.
- `tests/test_policy_engine.py` — unit tests.

## Run
From this folder:

```bash
python3 policy_engine.py
python3 -m unittest discover -s tests -v
```

## Shared interface to agree with teammates
An action has `id`, `cost`, `policy`, `preconditions`, and `effects` fields. The planner calls `check_policy(action_id, approved_actions)` before generating executable transitions. Outcomes:

- `allow`: may be used by a simulation of an action, subject to preconditions.
- `request_approval`: may be **recommended** or added as a pending approval request, but **not** simulated as executed.
- `deny`: cannot be part of an executable plan.

`check_policy` does not execute anything and intentionally does not check state preconditions or the goal; Tanuj's planning model will handle those. For experiments, the team should define a separate, deliberately unconstrained baseline planner that skips the checker.

## Future improvement
Use scoped approval records (action, incident, reviewer, expiration) instead of a simple set of action IDs. Add phishing and data-transfer scenarios after the first integration is tested.
