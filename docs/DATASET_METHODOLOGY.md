# Security Policy and Synthetic Dataset Methodology

## 1. Project Overview

This project evaluates security-constrained planning using four
classical artificial intelligence search algorithms:

- Breadth-First Search (BFS)
- Uniform-Cost Search (UCS)
- Greedy Best-First Search
- A* Search

The planner constructs simulated cybersecurity investigation plans.
A separate policy engine determines which actions are permitted,
require explicit human approval, or are prohibited.

No live cybersecurity systems are accessed or modified.

## 2. Research Objectives

The experimental work investigates:

1. How search algorithms differ in total plan cost.
2. How algorithms differ in nodes expanded and generated.
3. Whether security policies are enforced during planning.
4. Whether approval-required actions remain blocked without approval.
5. Whether dataset generation and experiments are reproducible.

## 3. Security Policy Engine

The expanded action registry contains 43 actions:

| Classification | Count |
|---|---:|
| Allowed | 28 |
| Approval required | 9 |
| Prohibited | 6 |
| Total | 43 |

Allowed actions can be selected by the planner.

Approval-required actions can be selected only when explicit approval
is supplied for that particular action.

Prohibited and unknown actions are denied.

The policy engine is separate from the search algorithms, allowing
policy enforcement to be applied consistently across BFS, UCS,
Greedy Best-First Search, and A*.

## 4. Synthetic Incident Categories

Three cybersecurity incident categories are modeled:

### Suspicious Login

Simulates investigation of suspicious authentication activity.

Example evidence includes login history, IP reputation,
device status, MFA activity, and account permissions.

### Phishing Email

Simulates investigation of a potentially malicious email.

Example evidence includes email headers, sender-domain verification,
URL reputation, and attachment analysis.

### Unusual Data Transfer

Simulates investigation of suspicious data movement.

Example evidence includes network logs, destination IP information,
data classification, user activity, and DLP alerts.

All evidence is synthetic.

## 5. Benchmark Dataset Design

The benchmark contains 90 generated scenarios:

| Category | Simple | Medium | Complex | Total |
|---|---:|---:|---:|---:|
| Suspicious login | 10 | 10 | 10 | 30 |
| Phishing | 10 | 10 | 10 | 30 |
| Data transfer | 10 | 10 | 10 | 30 |
| Total | 30 | 30 | 30 | 90 |

The generator is located at:

scripts/generate_dataset.py

The generated scenarios are stored under:

scenarios/benchmark/

The generator uses the existing experimental scenario templates.

## 6. Scenario Representation

Each scenario defines:

- A unique scenario identifier
- Initial evidence
- Required goal evidence
- Available investigation actions
- Synthetic action costs
- Action prerequisites
- Action effects
- Security policy classifications

An investigation reaches its goal when all required evidence
has been collected.

Action costs are synthetic nonnegative planning costs. They are not
measured investigation times, financial costs, or incident risks.

## 7. Complexity and Variation

The generator assigns three complexity labels:

- Simple: base investigation structure
- Medium: additional evidence requirements and dependencies
- Complex: more additional evidence requirements and dependencies

Some categories reuse actions already present in the base template.
Therefore, complexity is defined by the generation configuration,
not by a guaranteed identical action count for every category.

Scenario variations include changes to investigation action costs
and the relative cost of consolidated evidence-collection actions.

Consolidated actions can be cheaper, equally expensive, or more
expensive than their corresponding basic investigation paths.

The generated scenarios are controlled synthetic variations, not
90 independently collected real-world incidents.

## 8. Reproducibility

The generator uses a fixed random seed:

42

Generation command:

    python3 -m scripts.generate_dataset

Reproducibility was checked by hashing the benchmark directory
before and after regenerating all scenarios.

The complete directory SHA-256 hash was identical:

09c8a9cf2b3591820e989aed6f69cbe6dc404f12ffdd6ec36b1c15e6312af2ff

The hash includes relative file paths and file contents.

## 9. Benchmark Validation

All 90 scenarios were evaluated using:

- BFS
- UCS
- Greedy Best-First Search
- A*

This produced 360 initial planning runs.

Observed validation results:

| Metric | Result |
|---|---:|
| Benchmark scenarios | 90 |
| Planning runs | 360 |
| Successful planning runs | 360 |
| Failed planning runs | 0 |
| Policy violations in returned plans | 0 |
| UCS and A* cost agreement | 90/90 |

These checks confirm that the generated scenarios are solvable
under the tested policies and that returned actions are permitted.

They do not independently prove optimality against an external
reference solver.

## 10. Human-Approval Validation

Three additional scenarios test restricted containment actions:

- Suspicious login: revoke user sessions
- Phishing: quarantine email
- Data transfer: block network connection

Each scenario is tested with all four algorithms under two conditions:

1. Without approval
2. With explicit approval

Results:

- 24 of 24 validation runs passed.
- Without approval, the containment goal remained blocked.
- With explicit approval, the simulated containment goal was reachable.

These approval scenarios are separate from the 90 benchmark scenarios.

## 11. Automated Tests

The permanent test file is:

tests/test_security_dataset.py

The complete regression suite includes 53 tests.

Test command:

    python3 -m unittest discover -s tests -v

Last confirmed result:

    Ran 53 tests
    OK

The tests cover policy classification, default-deny behavior,
approval enforcement, benchmark distribution, unique identifiers,
scenario validity, planning success, and UCS/A* cost agreement.

## 12. Evaluation Metrics

The planner reports:

- Goal reached
- Selected actions
- Total plan cost
- Nodes expanded
- Nodes generated
- Maximum frontier size
- Search execution time
- Approval information

Performance metrics are stored in the planner result's
"metrics" dictionary.

Repeated timing measurements should be collected separately
for final algorithm-performance analysis.

## 13. Limitations

This study uses synthetic scenarios and simulated actions.

The dataset generator creates controlled variations from a small
number of base templates, limiting structural diversity.

Scenario complexity labels do not represent measured difficulty
on real-world cybersecurity investigations.

Action costs are illustrative rather than empirically calibrated.

Zero policy violations show compliance with the implemented
action-level rules on the tested cases, not complete security
against adversarial behavior.

The planner does not execute real containment actions.

The project does not currently evaluate LLM-based agents.

An unconstrained planning baseline, if implemented, should be
separate from the secure production planner.

## 14. Planned Extensions

Future experiments may include:

- Repeated timing trials
- Greater variation in search-space structure
- Additional unreachable-goal cases
- Prohibited-action shortcut scenarios
- Separate secure-versus-unconstrained planning comparisons
- More realistic investigation-cost estimates

## 15. Reproduction Commands

From the project root:

    python3 -m scripts.generate_dataset

    python3 -m unittest discover -s tests -v

The dataset and tests can be shared with other team members
without modifying the existing search-algorithm implementations.
