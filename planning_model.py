"""Validated, additive state-space model for synthetic investigations.

Evidence only accumulates. Approvals are supplied for one planning run and are
never invented by the search. The existing policy engine remains authoritative.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from policy_engine import ACTION_POLICIES, Decision, PolicyStatus, check_policy


def _strings(value: object, name: str) -> frozenset[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be a list of nonempty strings")
    return frozenset(value)


@dataclass(frozen=True)
class State:
    evidence: frozenset[str]
    approved_actions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Action:
    id: str
    cost: float | None
    policy: PolicyStatus
    preconditions: frozenset[str]
    effects: frozenset[str]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    initial_evidence: frozenset[str]
    required_evidence: frozenset[str]
    actions: tuple[Action, ...]

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        if not isinstance(data, dict):
            raise ValueError("Scenario must be a JSON object")
        scenario_id = data.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("scenario_id must be a nonempty string")
        initial = _strings(data.get("initial_evidence"), "initial_evidence")
        required = _strings(data.get("required_evidence"), "required_evidence")
        raw_actions = data.get("actions")
        if not isinstance(raw_actions, list):
            raise ValueError("actions must be a list")
        actions = []
        seen = set()
        for raw in raw_actions:
            if not isinstance(raw, dict):
                raise ValueError("Each action must be an object")
            action_id = raw.get("id")
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("Action id must be a nonempty string")
            if action_id in seen:
                raise ValueError(f"Duplicate action id: {action_id}")
            seen.add(action_id)
            try:
                policy = PolicyStatus(raw.get("policy"))
            except ValueError as exc:
                raise ValueError(f"Invalid policy for {action_id}") from exc
            authoritative = ACTION_POLICIES.get(action_id, PolicyStatus.PROHIBITED)
            if policy != authoritative:
                raise ValueError(f"Policy for {action_id} conflicts with policy_engine.py")
            cost = raw.get("cost")
            if cost is None:
                if policy != PolicyStatus.PROHIBITED:
                    raise ValueError(f"Executable action {action_id} needs a numeric cost")
            elif (
                isinstance(cost, bool)
                or not isinstance(cost, (int, float))
                or not math.isfinite(cost)
                or cost < 0
            ):
                raise ValueError(f"Cost for {action_id} must be finite and nonnegative")
            actions.append(Action(
                action_id, cost, policy,
                _strings(raw.get("preconditions"), f"{action_id}.preconditions"),
                _strings(raw.get("effects"), f"{action_id}.effects"),
            ))
        # Fixed ordering makes equal-priority choices reproducible.
        return cls(scenario_id, initial, required, tuple(sorted(actions, key=lambda a: a.id)))


def load_scenario(path: str | Path) -> Scenario:
    with Path(path).open(encoding="utf-8") as source:
        return Scenario.from_dict(json.load(source))


class InvestigationProblem:
    def __init__(self, scenario: Scenario, approved_actions: Iterable[str] = ()):
        if isinstance(approved_actions, str):
            raise ValueError("approved_actions must be a collection, not a string")
        approvals = frozenset(approved_actions)
        eligible = {a.id for a in scenario.actions if a.policy == PolicyStatus.APPROVAL_REQUIRED}
        if not approvals <= eligible:
            raise ValueError("Approvals must name approval-required actions in this scenario")
        self.scenario = scenario
        self.initial_state = State(scenario.initial_evidence, approvals)

    def is_goal(self, state: State) -> bool:
        return self.scenario.required_evidence <= state.evidence

    def successors(self, state: State):
        """Yield (action ID, next state, cost), enforcing policy before effects."""
        for action in self.scenario.actions:
            if not action.preconditions <= state.evidence:
                continue
            if check_policy(action.id, state.approved_actions).decision != Decision.ALLOW:
                continue
            evidence = state.evidence | action.effects
            if evidence == state.evidence:
                continue
            # Scenario validation guarantees executable actions have a cost.
            assert action.cost is not None
            yield action.id, State(evidence, state.approved_actions), action.cost

    def approval_requests(self, state: State) -> tuple[str, ...]:
        """Candidates enabled here; no request is granted or executed by this call."""
        return tuple(
            action.id for action in self.scenario.actions
            if action.preconditions <= state.evidence
            and not action.effects <= state.evidence
            and check_policy(action.id, state.approved_actions).decision == Decision.REQUEST_APPROVAL
        )

    def heuristic(self, state: State) -> float:
        """h-max: relaxed fact costs, using max rather than summing prerequisites.

        For each action, cost(effect) <= action cost + max(cost(prerequisites)).
        Taking the maximum goal-fact cost avoids double-counting shared work or
        actions with multiple effects. This underestimates real remaining cost
        for our nonnegative-cost, additive model. Unapproved actions stay blocked.
        """
        costs = {fact: 0.0 for fact in state.evidence}
        usable = [a for a in self.scenario.actions
                  if check_policy(a.id, state.approved_actions).decision == Decision.ALLOW]
        changed = True
        while changed:
            changed = False
            for action in usable:
                assert action.cost is not None
                estimate = action.cost + max(
                    (costs.get(fact, math.inf) for fact in action.preconditions), default=0.0
                )
                for effect in action.effects:
                    if estimate < costs.get(effect, math.inf):
                        costs[effect] = estimate
                        changed = True
        return max((costs.get(fact, math.inf) for fact in self.scenario.required_evidence), default=0.0)
