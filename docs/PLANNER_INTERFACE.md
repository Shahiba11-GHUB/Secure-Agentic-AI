# Planner interface and implementation notes

The search and state model are ready for integration and experiments. Everything
is synthetic and uses Python's standard library. Python 3.10+ is required; the
current test run used Python 3.14.

## Calling the planner

```python
from planning_model import load_scenario
from planner import plan

scenario = load_scenario("scenarios/suspicious_login.json")
result = plan(scenario, algorithm="astar")
# Algorithms: bfs, ucs, greedy, astar. Heuristics: hmax (default), zero.
```

`plan` returns a JSON-ready dictionary. A fresh problem is constructed for every
run, so approval state does not leak between algorithms or incidents. Jonathan
can call this function from an evaluation runner without parsing terminal text.
The lower-level `search_algorithms` module also accepts any object implementing
`initial_state`, `is_goal`, `successors`, and `heuristic`.

## State, actions, and goal

- A state contains immutable sets of evidence and granted action approvals.
- Actions have an ID, nonnegative finite cost, policy, prerequisites, and effects.
- Effects only add evidence. There are no delete effects, uncertain outcomes,
  or changing approvals within a search run.
- An action is available only when its prerequisites are satisfied and
  `check_policy` returns `allow`. No-effect actions are skipped.
- A goal state contains every item in `required_evidence`. An empty requirement
  set is already satisfied and produces a zero-cost empty plan.
- The JSON `goal` prose is descriptive, not executable logic. After reaching
  the evidence goal, the runner emits a fixed review recommendation. It makes
  no claim to infer whether the incident is malicious.

`policy_engine.py` is the authority for action categories. Loading a scenario
rejects conflicting declarations rather than letting the JSON override policy.
Unknown actions may appear only as prohibited and remain unexecutable. A new
allowed action therefore needs a deliberate addition to the policy engine.
Prohibited actions may keep their original `null` costs because constrained
search never places them in its frontier.

## Approval behavior

Pass `approved_actions=["force_password_reset"]` to `plan`, or use the CLI flag
`--approve force_password_reset`, only to represent an explicitly granted
simulated approval. The API rejects approvals for unknown, prohibited, or
already-allowed actions. These IDs are not authenticated human approval records;
the prototype trusts its caller, as the existing policy checker does.

An approval request does not create evidence or change the search state. If no
goal is reachable, `pending_approvals` reports distinct approval-required actions
whose prerequisites were satisfied somewhere in the explored space. These are
candidates for review, not a minimal or sufficient approval set. Prerequisite
steps may still need to be planned, and some candidates may be irrelevant to the
goal. After reviewing and granting an approval, rerun the planner. It does not
automatically grant approvals or return a plan that assumes they will be granted.

On success, `pending_approvals` is empty. `approved_actions_used` lists approved
actions in the returned plan, and `required_approvals` counts those actions. It
does not count every permission supplied by the caller or optional blocked actions.

## Algorithms and heuristic

| Algorithm | Frontier ordering | Duplicate handling | Guarantee in this model |
|---|---|---|---|
| BFS | FIFO | First discovery | Fewest actions |
| UCS | Accumulated cost | Keep cheaper paths, skip stale entries | Lowest cost |
| Greedy | Estimated remaining cost | First discovery | Finds a reachable goal in the finite space; no cost guarantee |
| A* | Accumulated cost + estimate | Keep cheaper paths and reopen improved states | Lowest cost with an admissible heuristic |

Scenario actions are sorted by ID. Priority ties use insertion order, never an
arbitrary comparison of states. Goal checks happen when a node is removed from
the frontier. Parent nodes are immutable, preserving the actual path even when
another cheaper route to the same state is discovered later.

The default heuristic is **h-max**. Facts already present have cost 0; other facts
start at infinity. Repeatedly relax each permitted action:

```text
estimated action completion cost = action cost + max(prerequisite fact costs)
estimated effect cost = min(previous effect cost, action completion cost)
h(state) = max(required fact costs)
```

The maximum over an empty prerequisite or goal set is 0. Unapproved and denied
actions are excluded. A fact with no permitted derivation keeps infinite cost;
search still explores the finite reachable space and can report approval candidates.

Why it is admissible: achieving all prerequisites costs at least as much as
achieving the most expensive one. Taking their maximum underestimates shared or
independent prerequisite work. Similarly, achieving all goal facts costs at
least as much as achieving any one of them. Taking a maximum instead of summing
avoids double-counting an action that supplies several facts. Relaxation over
all permitted actions can only lower the estimate. This argument relies on
nonnegative costs and additive effects. Revisit the heuristic if that model changes.

`--heuristic zero` gives the baseline h = 0; A* then behaves like UCS. A caller
supplying a custom heuristic to the search module is responsible for admissibility
and a zero value at goal states. The implementation rejects negative/NaN estimates.

## Results and metrics

| Field | Meaning |
|---|---|
| `goal_reached` | Whether a complete executable simulated plan was found |
| `actions` | Ordered action IDs; empty on failure |
| `total_cost` | Sum of returned plan costs; null on failure, 0 for an initial goal |
| `final_evidence` | Evidence after the successful plan; null on failure |
| `recommendation` | Fixed review message after success; null on failure |
| `nodes_expanded` | Non-goal nodes whose successors were examined; includes reopenings |
| `nodes_generated` | Successors yielded before duplicate filtering; excludes the root |
| `frontier_peak` | Maximum queued entries; includes stale priority-queue entries |
| `elapsed_seconds` | Search wall time, including heuristic and approval-candidate collection |

Elapsed time excludes file loading, scenario validation, problem construction,
and output formatting. It is not a complete application runtime or a statistical
benchmark. Jonathan should define repetitions, warm-ups, environment information,
and aggregation for the final evaluation. Node metrics are not unique-state counts.

## Validation and remaining evaluation work

The tests cover known optimal paths, shortest-versus-cheapest routes, greedy
suboptimality, repeated states, zero-cost cycles, stale entries, A* reopening,
unreachable and initially satisfied goals, policy enforcement, approvals, input
validation, CLI output, and h-max bounds on the reachable login states.

The two JSON fixtures under `tests/fixtures` use existing policy IDs with small,
made-up effects and costs solely to test behavior. They are not additional
realistic security scenarios or evidence for experimental performance claims.

Shahiba should add realistic alternative paths and approval-focused scenarios.
Jonathan should build the controlled evaluation runner, collect results, plot
comparisons, and implement the separately identified unconstrained baseline.
That baseline will need numeric experimental costs for prohibited actions and
independent policy-violation measurement. The production planner has no policy
bypass switch. The team still needs the final report, slides, and demo rehearsal.
