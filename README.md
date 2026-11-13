Secure Agentic AI: Policy-Constrained Cybersecurity Investigation Planning
AI Course Project | Kennesaw State University

Team: Shahiba Shamshad · Tanuj Tammalala · Jonathan Leon
Project overview
This project investigates how classical artificial intelligence search algorithms can generate efficient and policy-compliant cybersecurity investigation plans. Using simulated security alerts, we model an investigation as a state-space search problem and compare four planning strategies:
- Breadth-First Search (BFS)
- Uniform-Cost Search (UCS)
- Greedy Best-First Search
- A* Search
The planner must follow security rules during search, not merely filter an unsafe plan afterward. Each action is classified as allowed, requiring human approval, or prohibited. Approval-required actions may be proposed but are not treated as executed without authorization.

This is a research prototype. All incidents, actions, and costs are synthetic. It does not connect to or modify production security systems.
Research question
How do BFS, UCS, Greedy Best-First Search, and A* compare in finding low-cost investigation plans when security policies and human-approval requirements constrain the available actions?
Initial use case
The first scenario is a suspicious user login. Possible investigation steps include checking login history, reviewing IP reputation, inspecting device status, and recommending a follow-up action. Later scenarios may include phishing and unusual data transfers.

The intended workflow is:
1. Receive a simulated alert.
2. Represent collected evidence, permissions, and approval status as a search state.
3. Expand permissible investigation actions while enforcing policy constraints.
4. Generate a plan that meets the investigation goal.
5. Report actions, total plan cost, required approvals, and search-performance metrics.
Security policy model
Policy category	Example	Expected behavior
Allowed	Check login history	May be included as a simulated investigation action, subject to prerequisites
Approval required	Disable an account	Request human approval; do not treat the action as executed without approval
Prohibited	Delete security logs	Reject the action


Unknown actions are denied by default. In the initial module, policy classification is implemented; integration with the full state-transition planner is still pending.
Search algorithms and course concepts
Algorithm	Search criterion	Purpose
BFS	Fewest actions	Baseline for shortest plan by number of steps
UCS	Lowest accumulated action cost, g(n)	Find a minimum-cost plan
Greedy Best-First	Estimated remaining cost, h(n)	Examine heuristic-guided search
A*	g(n) + h(n)	Combine cumulative and estimated remaining cost


The project draws on class material about state-space search, uninformed vs. informed search, heuristic functions, and search efficiency. We plan to begin with an admissible baseline heuristic and compare search effort as problem size increases.
Team responsibilities
Member	Primary area	Responsibilities
Shahiba Shamshad	Security scenarios and policy engine	Define simulated incidents, action categories, approval rules, and policy tests
Tanuj Tammalala	Search algorithms and heuristics	Design the state-space representation; implement BFS, UCS, Greedy, and A*
Jonathan Leon	Integration and evaluation	Connect modules, develop test harnesses, collect metrics, and visualize results


All team members contribute to literature review, experimental validation, documentation, and presentation.
Repository structure (current and planned)
Secure-Agentic-AI/
├── policy_engine.py                 # Current: basic policy checker
├── scenarios/
│   └── suspicious_login.json       # Current: first synthetic incident
├── tests/
│   └── test_policy_engine.py       # Current: policy unit tests
├── search_algorithms.py            # Planned: teammate module
├── planner.py                      # Planned: state transitions and integration
├── evaluate.py                     # Planned: metrics and comparisons
├── results/                        # Planned: experiment outputs and figures
└── README.md
The planned files are not yet implemented. The repository will grow as team development progresses.
Run the current starter module
Prerequisite: Python 3.
# From the repository root
python3 policy_engine.py

# Run policy-engine unit tests
python3 -m unittest discover -s tests -v
The initial checker returns one of three decisions: allow, request_approval, or deny. It does not yet implement the search algorithms or execute any security action.
Evaluation plan
After integrating the search modules, the team will compare algorithms on:
- Execution time
- Number of states/nodes explored
- Total investigation plan cost
- Whether the goal state was reached
- Number of required human approvals
- Policy violations in a deliberately unconstrained baseline versus policy-constrained planning
Experiments will use shared synthetic scenarios, reproducible tie-breaking rules, and increasingly complex generated problems.
Project milestones
1. Model and policy definitions: Agree on shared action/state schema, costs, goals, and security rules.
2. Algorithm implementation: Implement BFS, UCS, Greedy Best-First, and A* with unit tests.
3. Integration: Enforce policy rules during successor generation and distinguish proposed actions from approved/executed actions.
4. Evaluation: Run controlled algorithm comparisons and visualize results.
5. Final submission: Complete report, presentation, and live demonstration.
Limitations and future work
The first version uses synthetic data and assumes investigation outcomes are known when planning; real investigations have uncertain observations. A future extension could incorporate LLM-suggested actions, with an independent policy checker enforcing authorization before execution. LLM integration is not part of the initial course scope.
References
- Course lecture slides: Advanced Search (UCS, Greedy Best-First, A*, heuristics)
- Course project instructions and sample project description
- Russell and Norvig, Artificial Intelligence: A Modern Approach (search chapters)
- NIST SP 800-61, Computer Security Incident Handling Guide (background reference; edition to be confirmed)
