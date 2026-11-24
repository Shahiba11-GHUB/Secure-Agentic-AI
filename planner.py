"""Command-line and Python entry points. All actions are simulations only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from planning_model import InvestigationProblem, Scenario, load_scenario
from policy_engine import PolicyStatus
from search_algorithms import search


def plan(scenario: Scenario, algorithm: str = "astar", approved_actions=(), heuristic: str = "hmax") -> dict:
    """Return JSON-ready results for the evaluation harness.

    On failure, pending_approvals lists candidates encountered in reachable
    states. They are not a promised solution or a minimum required approval set;
    some may need prerequisite steps first. Granting one requires a new run.
    On success, no additional approval is requested for the returned plan.
    """
    if heuristic not in {"hmax", "zero"}:
        raise ValueError(f"Unknown heuristic: {heuristic}")
    problem = InvestigationProblem(scenario, approved_actions)
    pending = set()
    result = search(
        problem, algorithm,
        heuristic=(lambda state: 0.0) if heuristic == "zero" else problem.heuristic,
        on_expand=lambda state: pending.update(problem.approval_requests(state)),
    )
    by_id = {a.id: a for a in scenario.actions}
    used_approvals = [a for a in result.actions if by_id[a].policy == PolicyStatus.APPROVAL_REQUIRED]
    return {
        "scenario_id": scenario.scenario_id,
        "algorithm": algorithm,
        "heuristic": heuristic if algorithm in {"greedy", "astar"} else None,
        "goal_reached": result.goal_reached,
        "actions": list(result.actions),
        "total_cost": result.total_cost,
        "final_evidence": sorted(result.states[-1].evidence) if result.goal_reached else None,
        "required_approvals": len(used_approvals),
        "approved_actions_used": used_approvals,
        "pending_approvals": [] if result.goal_reached else sorted(pending),
        "approval_note": (
            "No additional approval is needed for this simulated plan."
            if result.goal_reached else
            "Candidates were found in reachable states; granting them does not guarantee a solution. "
            "Review prerequisites and rerun with explicitly granted approvals."
        ),
        "recommendation": (
            "Required evidence collected. Review the simulated findings before deciding on any further response."
            if result.goal_reached else None
        ),
        "metrics": {
            "nodes_expanded": result.nodes_expanded,
            "nodes_generated": result.nodes_generated,
            "frontier_peak": result.frontier_peak,
            "elapsed_seconds": result.elapsed_seconds,
        },
        "simulation_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", type=Path,
                        default=Path(__file__).parent / "scenarios" / "suspicious_login.json")
    parser.add_argument("--algorithm", choices=["bfs", "ucs", "greedy", "astar", "all"], default="astar")
    parser.add_argument("--approve", action="append", default=[], metavar="ACTION_ID",
                        help="Record an explicitly granted simulated approval; repeat for multiple actions")
    parser.add_argument("--heuristic", choices=["hmax", "zero"], default="hmax")
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        algorithms = ["bfs", "ucs", "greedy", "astar"] if args.algorithm == "all" else [args.algorithm]
        results = [plan(scenario, name, args.approve, args.heuristic) for name in algorithms]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(results if args.algorithm == "all" else results[0], indent=2, allow_nan=False))
    return 0 if all(result["goal_reached"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
