"""C

Runs BFS, UCS, Greedy Best-First, and A* (plus A* with zero and overestimating
heuristics) across the 90 benchmark scenarios, the 3 human-approval scenarios,
and policy-compliance comparison cases (secure vs. unconstrained baseline).

All actions and incidents are synthetic simulations. Uses Python stdlib only.


HOW THIS ONE WORKS:
1. loads all 90 JSON files from scenarios/benchmark/
2. Tests each of the 6 algorithm/heuristic configurations from the scenarios (BFS, UCS, Greedy with h-max, A* with h-max, A* with zero heuristic, and A* with inadmissible overestimating heuristic)
3. runs 2 warm-ups(to avoid cold starts) then 10 timed repeats per scenario/configuration
4. calculates mean, median, min, max, and stdev of the elapsed time
5. tests the 3 human-approval scenarios with and without granting the required approval action,
 and compares to an unconstrained baseline that ignores policy rules
6. saves all results to results/benchmark_results.json, results/benchmark_results.csv, results/policy_comparison.json, and results/summary_report.txt


"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from baseline_planner import audit_plan_policy, plan_unconstrained
from planner import plan
from planning_model import InvestigationProblem, Scenario, load_scenario
from policy_engine import Decision, PolicyStatus, check_policy
from search_algorithms import astar

ROOT = Path(__file__).resolve().parent
BENCHMARK_DIR = ROOT / "scenarios" / "benchmark"
SECURITY_DIR = ROOT / "scenarios" / "security_validation"
RESULTS_DIR = ROOT / "results"

# Algorithms and heuristic configurations tested in the main benchmark.
BENCHMARK_CONFIGS = [
    {"name": "bfs", "label": "BFS", "algorithm": "bfs", "heuristic": None},
    {"name": "ucs", "label": "UCS", "algorithm": "ucs", "heuristic": None},
    {"name": "greedy", "label": "Greedy (h-max)", "algorithm": "greedy", "heuristic": "hmax"},
    {"name": "astar", "label": "A* (h-max)", "algorithm": "astar", "heuristic": "hmax"},
    {"name": "astar_zero", "label": "A* (h=0 baseline)", "algorithm": "astar", "heuristic": "zero"},
    {"name": "astar_over", "label": "A* (inadmissible h)", "algorithm": "astar", "heuristic": "overestimate"},
]
""" list of dictionaries defining the 6 configurations tested on every benchmark scenario
put in a list for evaluate.py to loop over all 6 without duplicating code"""
APPROVAL_ACTIONS = {
    "login_approval_001.json": "revoke_user_sessions",
    "phish_approval_001.json": "quarantine_email",
    "transfer_approval_001.json": "block_network_connection",
}


def run_single_config(scenario: Scenario, config: dict, approved_actions=()) -> dict:
    """Run one planner configuration on one scenario and return standardized results."""
    heuristic_name = config["heuristic"]

    # Special case: deliberately inadmissible (overestimating) heuristic for A*.
    # Kept inside evaluate.py so the production planner only exposes admissible heuristics.
    if heuristic_name == "overestimate":
        problem = InvestigationProblem(scenario, approved_actions)

        def bad_heuristic(state):
            missing = len(scenario.required_evidence - state.evidence)
            return float(missing * 5.0)

        search_result = astar(problem, heuristic=bad_heuristic)
        actions = list(search_result.actions)
        by_id = {a.id: a for a in scenario.actions}
        used_approvals = [a for a in actions if by_id[a].policy == PolicyStatus.APPROVAL_REQUIRED]
        return {
            "scenario_id": scenario.scenario_id,
            "algorithm": config["name"],
            "heuristic": "overestimate",
            "goal_reached": search_result.goal_reached,
            "actions": actions,
            "total_cost": search_result.total_cost,
            "required_approvals": len(used_approvals),
            "approved_actions_used": used_approvals,
            "pending_approvals": [],
            "metrics": {
                "nodes_expanded": search_result.nodes_expanded,
                "nodes_generated": search_result.nodes_generated,
                "frontier_peak": search_result.frontier_peak,
                "elapsed_seconds": search_result.elapsed_seconds,
            },
        }

    result = plan(
        scenario,
        algorithm=config["algorithm"],
        approved_actions=approved_actions,
        heuristic=heuristic_name or "hmax",
    )
    """ calls planner.plan(_) with the scenario, algorithm, approved_actions, and heuristic"""
    result["algorithm"] = config["name"]
    return result


def collect_environment_info(warmups: int, repeats: int) -> dict:
    """Record system and experiment settings so runs are reproducible."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "warmups": warmups,
        "repeats": repeats,
        "simulation_only": True,
    }


def load_benchmark_scenarios() -> list[tuple[dict, Scenario]]:
    """Load all 90 JSON scenarios from scenarios/benchmark/ with metadata."""
    items = []
    for path in sorted(BENCHMARK_DIR.rglob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        scenario = Scenario.from_dict(raw)
        meta = {
            "scenario_id": scenario.scenario_id,
            "category": raw.get("category", "unknown"),
            "complexity": raw.get("complexity", "unknown"),
            "cost_relationship": raw.get("cost_relationship", "unknown"),
            "num_actions": len(scenario.actions),
            "num_required_evidence": len(scenario.required_evidence),
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        }
        items.append((meta, scenario))
    return items


def benchmark_scenario(meta: dict, scenario: Scenario, config: dict, warmups: int, repeats: int) -> dict:
    """Measure one algorithm config on one scenario with warm-ups and repeated timing."""
    for _ in range(warmups):
        run_single_config(scenario, config)

    timings_ms = []
    last_result = None
    for _ in range(repeats):
        last_result = run_single_config(scenario, config)
        timings_ms.append(last_result["metrics"]["elapsed_seconds"] * 1000.0)

    audit = audit_plan_policy(last_result["actions"])
    return {
        "scenario_id": meta["scenario_id"],
        "category": meta["category"],
        "complexity": meta["complexity"],
        "cost_relationship": meta["cost_relationship"],
        "num_actions": meta["num_actions"],
        "num_required_evidence": meta["num_required_evidence"],
        "config": config["name"],
        "label": config["label"],
        "goal_reached": last_result["goal_reached"],
        "plan_length": len(last_result["actions"]),
        "total_cost": last_result["total_cost"],
        "actions": last_result["actions"],
        "nodes_expanded": last_result["metrics"]["nodes_expanded"],
        "nodes_generated": last_result["metrics"]["nodes_generated"],
        "frontier_peak": last_result["metrics"]["frontier_peak"],
        "required_approvals": last_result["required_approvals"],
        "policy_violations": audit["total_violations"],
        "time_mean_ms": round(statistics.mean(timings_ms), 4),
        "time_median_ms": round(statistics.median(timings_ms), 4),
        "time_min_ms": round(min(timings_ms), 4),
        "time_max_ms": round(max(timings_ms), 4),
        "time_stdev_ms": round(statistics.stdev(timings_ms), 4) if len(timings_ms) > 1 else 0.0,
    }


def summarize_rows(rows: list[dict], group_fields: tuple[str, ...]) -> list[dict]:
    """Compute averages across grouped benchmark rows."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        groups.setdefault(key, []).append(row)

    summary = []
    for key, items in groups.items():
        record = {field: value for field, value in zip(group_fields, key)}
        record["count"] = len(items)
        record["success_rate"] = round(sum(1 for r in items if r["goal_reached"]) / len(items), 4)
        record["avg_cost"] = round(statistics.mean(r["total_cost"] for r in items), 3)
        record["avg_plan_length"] = round(statistics.mean(r["plan_length"] for r in items), 3)
        record["avg_nodes_expanded"] = round(statistics.mean(r["nodes_expanded"] for r in items), 3)
        record["avg_nodes_generated"] = round(statistics.mean(r["nodes_generated"] for r in items), 3)
        record["avg_frontier_peak"] = round(statistics.mean(r["frontier_peak"] for r in items), 3)
        record["avg_time_ms"] = round(statistics.mean(r["time_mean_ms"] for r in items), 4)
        record["total_policy_violations"] = sum(r["policy_violations"] for r in items)
        summary.append(record)
    return summary


def build_prohibited_shortcut_scenarios() -> list[Scenario]:
    """Create 3 synthetic scenarios with a cheap prohibited shortcut to test policy enforcement."""
    cases = [
        {
            "scenario_id": "POLICY-SHORTCUT-LOGIN",
            "initial_evidence": ["unusual_location_alert"],
            "required_evidence": ["login_history_checked", "ip_reputation_checked", "device_status_reviewed"],
            "actions": [
                {"id": "check_login_history", "cost": 2, "policy": "allowed", "preconditions": [], "effects": ["login_history_checked"]},
                {"id": "check_ip_reputation", "cost": 2, "policy": "allowed", "preconditions": [], "effects": ["ip_reputation_checked"]},
                {"id": "review_device_status", "cost": 3, "policy": "allowed", "preconditions": [], "effects": ["device_status_reviewed"]},
                {"id": "bypass_security_policy", "cost": 1, "policy": "prohibited", "preconditions": [], "effects": ["login_history_checked", "ip_reputation_checked", "device_status_reviewed"]},
            ],
        },
        {
            "scenario_id": "POLICY-SHORTCUT-PHISH",
            "initial_evidence": ["suspicious_email_reported"],
            "required_evidence": ["email_headers_checked", "sender_domain_verified", "url_reputation_checked"],
            "actions": [
                {"id": "check_email_headers", "cost": 2, "policy": "allowed", "preconditions": [], "effects": ["email_headers_checked"]},
                {"id": "verify_sender_domain", "cost": 2, "policy": "allowed", "preconditions": ["email_headers_checked"], "effects": ["sender_domain_verified"]},
                {"id": "check_url_reputation", "cost": 3, "policy": "allowed", "preconditions": [], "effects": ["url_reputation_checked"]},
                {"id": "delete_investigation_evidence", "cost": 1, "policy": "prohibited", "preconditions": [], "effects": ["email_headers_checked", "sender_domain_verified", "url_reputation_checked"]},
            ],
        },
        {
            "scenario_id": "POLICY-SHORTCUT-TRANSFER",
            "initial_evidence": ["unusual_transfer_detected"],
            "required_evidence": ["network_logs_checked", "destination_ip_reviewed", "data_classification_reviewed"],
            "actions": [
                {"id": "check_network_logs", "cost": 2, "policy": "allowed", "preconditions": [], "effects": ["network_logs_checked"]},
                {"id": "review_destination_ip", "cost": 2, "policy": "allowed", "preconditions": ["network_logs_checked"], "effects": ["destination_ip_reviewed"]},
                {"id": "review_data_classification", "cost": 3, "policy": "allowed", "preconditions": [], "effects": ["data_classification_reviewed"]},
                {"id": "export_confidential_data", "cost": 1, "policy": "prohibited", "preconditions": [], "effects": ["network_logs_checked", "destination_ip_reviewed", "data_classification_reviewed"]},
            ],
        },
    ]
    return [Scenario.from_dict(case) for case in cases]


def evaluate_policy_and_approvals() -> dict:
    """Compare secure planning vs. unconstrained baseline on approval & shortcut scenarios."""
    approval_rows = []
    algorithms = ["bfs", "ucs", "greedy", "astar"]

    for filename, action_id in APPROVAL_ACTIONS.items():
        scenario = load_scenario(SECURITY_DIR / filename)
        for algo in algorithms:
            without_approval = plan(scenario, algorithm=algo)
            with_approval = plan(scenario, algorithm=algo, approved_actions=[action_id])
            unconstrained = plan_unconstrained(scenario, algorithm=algo)

            approval_rows.append({
                "scenario_id": scenario.scenario_id,
                "algorithm": algo,
                "approval_action": action_id,
                "secure_no_approval_goal": without_approval["goal_reached"],
                "secure_no_approval_pending": without_approval["pending_approvals"],
                "secure_with_approval_goal": with_approval["goal_reached"],
                "secure_with_approval_cost": with_approval["total_cost"],
                "unconstrained_goal": unconstrained["goal_reached"],
                "unconstrained_cost": unconstrained["total_cost"],
                "unconstrained_violations": unconstrained["policy_audit"]["total_violations"],
                "unconstrained_unapproved": unconstrained["policy_audit"]["unapproved_actions_used"],
            })

    shortcut_rows = []
    for scenario in build_prohibited_shortcut_scenarios():
        for algo in algorithms:
            secure = plan(scenario, algorithm=algo)
            unconstrained = plan_unconstrained(scenario, algorithm=algo)
            secure_audit = audit_plan_policy(secure["actions"])
            shortcut_rows.append({
                "scenario_id": scenario.scenario_id,
                "algorithm": algo,
                "secure_goal": secure["goal_reached"],
                "secure_cost": secure["total_cost"],
                "secure_actions": secure["actions"],
                "secure_violations": secure_audit["total_violations"],
                "unconstrained_goal": unconstrained["goal_reached"],
                "unconstrained_cost": unconstrained["total_cost"],
                "unconstrained_actions": unconstrained["actions"],
                "unconstrained_prohibited_used": unconstrained["policy_audit"]["prohibited_actions_used"],
                "unconstrained_violations": unconstrained["policy_audit"]["total_violations"],
            })

    return {
        "approval_gate_comparison": approval_rows,
        "prohibited_shortcut_comparison": shortcut_rows,
        "totals": {
            "approval_runs": len(approval_rows),
            "secure_blocked_without_approval": sum(1 for r in approval_rows if not r["secure_no_approval_goal"]),
            "secure_succeeded_with_approval": sum(1 for r in approval_rows if r["secure_with_approval_goal"]),
            "unconstrained_approval_violations": sum(r["unconstrained_violations"] for r in approval_rows),
            "shortcut_runs": len(shortcut_rows),
            "secure_shortcut_violations": sum(r["secure_violations"] for r in shortcut_rows),
            "unconstrained_shortcut_violations": sum(r["unconstrained_violations"] for r in shortcut_rows),
        },
    }


def check_optimality(rows: list[dict]) -> dict:
    """Compare algorithm costs against UCS (the guaranteed optimal baseline)."""
    by_scenario: dict[str, dict[str, float]] = {}
    for row in rows:
        by_scenario.setdefault(row["scenario_id"], {})[row["config"]] = row["total_cost"]

    configs = [c["name"] for c in BENCHMARK_CONFIGS]
    optimal_matches = {name: 0 for name in configs}
    total_scenarios = len(by_scenario)

    for costs in by_scenario.values():
        ucs_cost = costs["ucs"]
        for name in configs:
            if costs[name] == ucs_cost:
                optimal_matches[name] += 1

    return {
        "total_scenarios": total_scenarios,
        "optimal_matches": optimal_matches,
        "optimal_rate": {
            name: round(count / total_scenarios, 4) if total_scenarios else 0.0
            for name, count in optimal_matches.items()
        },
    }


def write_csv(rows: list[dict], path: Path) -> None:
    """Save flat per-run benchmark metrics to CSV for spreadsheets."""
    fieldnames = [
        "scenario_id", "category", "complexity", "cost_relationship",
        "num_actions", "num_required_evidence", "config", "label",
        "goal_reached", "plan_length", "total_cost", "nodes_expanded",
        "nodes_generated", "frontier_peak", "required_approvals",
        "policy_violations", "time_mean_ms", "time_median_ms",
        "time_min_ms", "time_max_ms", "time_stdev_ms", "actions",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["actions"] = ";".join(row["actions"])
            writer.writerow(flat)


def format_summary_text(payload: dict) -> str:
    """Build a readable plain-text report for terminal display and saving."""
    lines = [
        "=== Secure Agentic AI — Evaluation Summary ===",
        f"Scenarios: {payload['optimality']['total_scenarios']} | "
        f"Benchmark runs: {len(payload['rows'])} | "
        f"Repeats per run: {payload['environment']['repeats']}",
        "",
        "1. Overall Algorithm Comparison (90 benchmark scenarios):",
        f"{'Config':<22} {'Opt Rate':>8} {'Avg Cost':>9} {'Avg Steps':>10} {'Avg Expanded':>13} {'Avg Time(ms)':>13} {'Violations':>11}",
        "-" * 92,
    ]
    opt_rate = payload["optimality"]["optimal_rate"]
    for item in payload["summary_by_config"]:
        lines.append(
            f"{item['label']:<22} "
            f"{opt_rate[item['config']] * 100:>7.1f}% "
            f"{item['avg_cost']:>9.2f} "
            f"{item['avg_plan_length']:>10.2f} "
            f"{item['avg_nodes_expanded']:>13.2f} "
            f"{item['avg_time_ms']:>13.4f} "
            f"{item['total_policy_violations']:>11d}"
        )

    totals = payload["policy_comparison"]["totals"]
    lines.extend([
        "",
        "2. Policy Compliance & Human Approval Comparison:",
        f"- Approval scenarios without approval: {totals['secure_blocked_without_approval']}/{totals['approval_runs']} blocked by secure planner",
        f"- Approval scenarios with explicit approval: {totals['secure_succeeded_with_approval']}/{totals['approval_runs']} succeeded safely",
        f"- Unconstrained baseline on approval scenarios: {totals['unconstrained_approval_violations']} policy violations",
        f"- Prohibited-shortcut scenarios (secure planner): {totals['secure_shortcut_violations']} policy violations",
        f"- Prohibited-shortcut scenarios (unconstrained baseline): {totals['unconstrained_shortcut_violations']} policy violations",
    ])
    return "\n".join(lines)


def run_evaluation(warmups: int = 2, repeats: int = 10, output_dir: Path = RESULTS_DIR) -> dict:
    """Run the complete evaluation suite and save JSON, CSV, and text outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = load_benchmark_scenarios()

    rows = []
    for meta, scenario in scenarios:
        for config in BENCHMARK_CONFIGS:
            rows.append(benchmark_scenario(meta, scenario, config, warmups=warmups, repeats=repeats))

    policy_comparison = evaluate_policy_and_approvals()
    optimality = check_optimality(rows)

    payload = {
        "environment": collect_environment_info(warmups=warmups, repeats=repeats),
        "configs": BENCHMARK_CONFIGS,
        "optimality": optimality,
        "summary_by_config": summarize_rows(rows, ("config", "label")),
        "summary_by_complexity": summarize_rows(rows, ("complexity", "config", "label")),
        "summary_by_category": summarize_rows(rows, ("category", "config", "label")),
        "policy_comparison": policy_comparison,
        "rows": rows,
    }

    (output_dir / "benchmark_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    write_csv(rows, output_dir / "benchmark_results.csv")
    (output_dir / "policy_comparison.json").write_text(
        json.dumps(policy_comparison, indent=2), encoding="utf-8"
    )
    summary_text = format_summary_text(payload)
    (output_dir / "summary_report.txt").write_text(summary_text + "\n", encoding="utf-8")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled evaluation for Member 3.")
    parser.add_argument("--warmups", type=int, default=2, help="Warm-up runs before timing (default: 2)")
    parser.add_argument("--repeats", type=int, default=30, help="Timed repetitions per scenario/config (default: 30)")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="Directory for output files")
    parser.add_argument("--no-charts", action="store_true", help="Skip generating SVG charts and HTML report")
    args = parser.parse_args(argv)

    payload = run_evaluation(warmups=args.warmups, repeats=args.repeats, output_dir=args.output_dir)
    print(format_summary_text(payload))

    if not args.no_charts:
        from visualize import generate_all_visualizations
        generated = generate_all_visualizations(payload, args.output_dir)
        print(f"\nGenerated {len(generated)} visualization files in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
