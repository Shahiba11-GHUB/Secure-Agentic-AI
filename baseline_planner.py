"""Unconstrained search baseline for policy-compliance comparison ONLY.

This module is intentionally separate from the secure production planner
(planner.py and planning_model.py). It ignores security policy rules so that
experiments can measure how many policy violations would happen if a planner
did NOT enforce allowed / approval-required / prohibited rules during search.

Steps on how this works:
1. Unconstrained problem -> works like InvestigationProblem (from planning_model.py) but ignores policy checks by skipping
check_poolicy(). if a prohibited action has no cost / cost=None, we give it a cost of 1 so search algorithms can still use it!

2. plan unconstrained() -> runs search on the unconstrained problem, then audits the resulting plan for policy violations using audit_plan_policy() (which uses check_policy() from
    policy_engine.py).


"""
from __future__ import annotations

import math

from planning_model import Scenario, State
from policy_engine import Decision, PolicyStatus, check_policy
from search_algorithms import search


class UnconstrainedProblem:
    """Search problem that ignores policy checks for experimental comparison."""

    def __init__(self, scenario: Scenario, default_prohibited_cost: float = 1.0):
        self.scenario = scenario
        self.default_prohibited_cost = default_prohibited_cost
        self.initial_state = State(scenario.initial_evidence)

    def is_goal(self, state: State) -> bool:
        return self.scenario.required_evidence <= state.evidence
    """ create search problem object that matches shape of search() (initial_state, is_goal(), successors(), heuristic()) 
    store scenario and fallback cost(1.0) for prohibited actions of no cost
    is_goal() checks if all required evidence is inside state.evidence """

    def successors(self, state: State):
        """Yield all actions whose preconditions are met, ignoring policy rules."""
        for action in self.scenario.actions:
            if not action.preconditions <= state.evidence:
                continue
            next_evidence = state.evidence | action.effects
            if next_evidence == state.evidence:
                continue
            # Prohibited actions may have cost=None in scenarios; give them a
            # cost of 1 so the unconstrained baseline can test them.
            cost = self.default_prohibited_cost if action.cost is None else action.cost
            yield action.id, State(next_evidence), cost
        # ^ mirrors InvestigationProblem.successors() from planning_model.py, and minus check_policy() from policy_engine.py
    """ This will lopp over every action, checking preconditions met and skips no-op actions that add no new evidence
    (if next_evidence == state.evidence) does not use check_policy(), to allow prohibited / unapproved actions"""

    def heuristic(self, state: State) -> float:
        """Relaxed h-max heuristic over all actions without policy filtering."""
        costs = {fact: 0.0 for fact in state.evidence}
        changed = True
        while changed:
            changed = False
            for action in self.scenario.actions:
                step_cost = self.default_prohibited_cost if action.cost is None else action.cost
                estimate = step_cost + max(
                    (costs.get(fact, math.inf) for fact in action.preconditions),
                    default=0.0,
                )
                for effect in action.effects:
                    if estimate < costs.get(effect, math.inf):
                        costs[effect] = estimate
                        changed = True
        return max(
            (costs.get(fact, math.inf) for fact in self.scenario.required_evidence),
            default=0.0,
        )
    """ ^ Computes the h-max heuristic over all actions (ignoring policy rules)
    Facts already in state evidence ost 0, the while loop repeatedly updates the cheapest estimated cost to unlovk each fact
    until nothing improves, then returns the max cost of still missing goal facts."""


def audit_plan_policy(actions: list[str] | tuple[str, ...], approved_actions=()) -> dict:
    """Independently check every action in a plan against policy_engine.py."""
    prohibited_actions = []
    unapproved_actions = []

    for action_id in actions:
        policy_result = check_policy(action_id, approved_actions)
        if policy_result.decision == Decision.DENY:
            prohibited_actions.append(action_id)
        elif policy_result.decision == Decision.REQUEST_APPROVAL:
            unapproved_actions.append(action_id)

    total_violations = len(prohibited_actions) + len(unapproved_actions)
    return {
        "prohibited_violations": len(prohibited_actions),
        "unapproved_violations": len(unapproved_actions),
        "total_violations": total_violations,
        "prohibited_actions_used": prohibited_actions,
        "unapproved_actions_used": unapproved_actions,
        "compliant": total_violations == 0,
    }
#INdependent violation counter ^
""" Take any list of action IDs produceds by any planner and use check_policy() to judge each step. 
 Actions that returns Decsion.Deny counts as prohibited violation, and Decision.Request_Approval counts as unapproved violation."""


def plan_unconstrained(
    scenario: Scenario,
    algorithm: str = "astar",
    heuristic: str = "hmax",
    default_prohibited_cost: float = 1.0,
) -> dict:
    """Run search WITHOUT policy enforcement and measure policy violations."""
    if heuristic not in {"hmax", "zero"}:
        raise ValueError(f"Unknown heuristic: {heuristic}")

    problem = UnconstrainedProblem(scenario, default_prohibited_cost=default_prohibited_cost)
    result = search(
        problem,
        algorithm,
        heuristic=(lambda state: 0.0) if heuristic == "zero" else problem.heuristic,
    )
    audit = audit_plan_policy(result.actions)
    by_id = {action.id: action for action in scenario.actions}
    approval_actions = [
        action_id for action_id in result.actions
        if by_id[action_id].policy == PolicyStatus.APPROVAL_REQUIRED
    ]

    return {
        "scenario_id": scenario.scenario_id,
        "algorithm": algorithm,
        "heuristic": heuristic if algorithm in {"greedy", "astar"} else None,
        "goal_reached": result.goal_reached,
        "actions": list(result.actions),
        "total_cost": result.total_cost,
        "required_approvals": len(approval_actions),
        "policy_audit": audit,
        "metrics": {
            "nodes_expanded": result.nodes_expanded,
            "nodes_generated": result.nodes_generated,
            "frontier_peak": result.frontier_peak,
            "elapsed_seconds": result.elapsed_seconds,
        },
        "simulation_only": True,
        "unconstrained_baseline": True,
    }
""" wraps the scenario in Unconstrained Problem, runs search(), audits with audit_plan_policy, and returns
a dictionary that matches shape of planner.plan() (JSON ready)
"""