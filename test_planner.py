import contextlib
import copy
import io
import json
import math
from pathlib import Path
import unittest

from planner import main, plan
from planning_model import InvestigationProblem, Scenario, State, load_scenario
from search_algorithms import astar, ucs


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
ALGORITHMS = ("bfs", "ucs", "greedy", "astar")


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.login = load_scenario(ROOT / "scenarios" / "suspicious_login.json")
        self.approval = load_scenario(FIXTURES / "approval_gate.json")

    def test_login_all_algorithms_collect_evidence_at_cost_four(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                result = plan(self.login, algorithm)
                self.assertTrue(result["goal_reached"])
                self.assertEqual(result["total_cost"], 4)
                self.assertEqual(set(result["actions"]), {"check_login_history", "check_ip_reputation", "review_device_status"})
                self.assertTrue(self.login.required_evidence <= set(result["final_evidence"]))
                self.assertEqual(result["pending_approvals"], [])
                self.assertEqual(result["required_approvals"], 0)
                self.assertIsNotNone(result["recommendation"])

    def test_tradeoff_fixture_distinguishes_algorithms(self):
        scenario = load_scenario(FIXTURES / "cost_tradeoff.json")
        expected = {"bfs": 7, "greedy": 7, "ucs": 2, "astar": 2}
        for algorithm, cost in expected.items():
            self.assertEqual(plan(scenario, algorithm)["total_cost"], cost)

    def test_no_approval_means_no_effects_or_false_success(self):
        for algorithm in ALGORITHMS:
            result = plan(self.approval, algorithm)
            self.assertFalse(result["goal_reached"])
            self.assertIsNone(result["total_cost"])
            self.assertIsNone(result["final_evidence"])
            self.assertIsNone(result["recommendation"])
            self.assertEqual(result["actions"], [])
            self.assertEqual(result["pending_approvals"], ["force_password_reset"])

    def test_explicit_approval_allows_simulated_reset_after_prerequisite(self):
        for algorithm in ALGORITHMS:
            result = plan(self.approval, algorithm, ["force_password_reset"])
            self.assertEqual(result["actions"], ["check_login_history", "force_password_reset"])
            self.assertEqual(result["total_cost"], 6)
            self.assertEqual(result["required_approvals"], 1)
            self.assertEqual(result["approved_actions_used"], ["force_password_reset"])
            self.assertEqual(result["pending_approvals"], [])

    def test_approvals_do_not_leak_between_runs(self):
        self.assertTrue(plan(self.approval, approved_actions=["force_password_reset"])["goal_reached"])
        self.assertFalse(plan(self.approval)["goal_reached"])

    def test_invalid_approvals_are_rejected(self):
        for approvals in (["delete_logs"], ["unknown_action"], ["check_login_history"], "force_password_reset"):
            with self.subTest(approvals=approvals), self.assertRaises(ValueError):
                plan(self.approval, approved_actions=approvals)

    def test_preconditions_policy_and_no_op_filtering(self):
        problem = InvestigationProblem(self.approval, ["force_password_reset"])
        first = list(problem.successors(problem.initial_state))
        self.assertEqual([a for a, _, _ in first], ["check_login_history"])
        second = list(problem.successors(first[0][1]))
        self.assertEqual([a for a, _, _ in second], ["force_password_reset"])
        self.assertEqual(list(problem.successors(second[0][1])), [])

    def test_prohibited_and_unknown_actions_cannot_supply_goal_evidence(self):
        for action_id in ("delete_logs", "unrecognized_action"):
            scenario = Scenario.from_dict({
                "scenario_id": "deny", "initial_evidence": [], "required_evidence": ["done"],
                "actions": [{"id": action_id, "cost": None, "policy": "prohibited", "preconditions": [], "effects": ["done"]}],
            })
            for algorithm in ALGORITHMS:
                result = plan(scenario, algorithm)
                self.assertFalse(result["goal_reached"])
                self.assertEqual(result["pending_approvals"], [])

    def test_state_identity_is_order_independent_and_includes_approvals(self):
        a = State(frozenset(["x", "y"]))
        b = State(frozenset(["y", "x"]))
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, State(a.evidence, frozenset(["disable_account"])))

    def test_hmax_avoids_double_counting_multiple_effects(self):
        scenario = Scenario.from_dict({
            "scenario_id": "bundle", "initial_evidence": [], "required_evidence": ["a", "b"],
            "actions": [{"id": "scan_device", "cost": 1, "policy": "allowed", "preconditions": [], "effects": ["a", "b"]}],
        })
        problem = InvestigationProblem(scenario)
        self.assertEqual(problem.heuristic(problem.initial_state), 1)
        self.assertEqual(astar(problem).total_cost, 1)

    def test_hmax_respects_approval_and_goal(self):
        blocked = InvestigationProblem(self.approval)
        allowed = InvestigationProblem(self.approval, ["force_password_reset"])
        self.assertEqual(blocked.heuristic(blocked.initial_state), math.inf)
        self.assertEqual(allowed.heuristic(allowed.initial_state), 6)
        self.assertEqual(allowed.heuristic(State(frozenset(["password_reset_completed"]))), 0)

    def test_hmax_is_lower_bound_for_every_reachable_login_state(self):
        problem = InvestigationProblem(self.login)
        seen, todo = {problem.initial_state}, [problem.initial_state]
        while todo:
            state = todo.pop()
            remaining = InvestigationProblem(self.login)
            remaining.initial_state = state
            optimal = ucs(remaining)
            self.assertTrue(optimal.goal_reached)
            self.assertLessEqual(problem.heuristic(state), optimal.total_cost)
            self.assertEqual(astar(remaining).total_cost, optimal.total_cost)
            for _, successor, _ in problem.successors(state):
                if successor not in seen:
                    seen.add(successor)
                    todo.append(successor)

    def test_cli_all_outputs_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([str(ROOT / "scenarios" / "suspicious_login.json"), "--algorithm", "all"])
        results = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual([r["algorithm"] for r in results], list(ALGORITHMS))

    def test_cli_failure_and_approved_rerun(self):
        for args, expected in (([], 1), (["--approve", "force_password_reset"], 0)):
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([str(FIXTURES / "approval_gate.json"), *args])
            self.assertEqual(code, expected)

    def test_cli_bad_file_has_clear_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as raised:
            main([str(FIXTURES / "missing.json")])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("error:", error.getvalue())


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((FIXTURES / "cost_tradeoff.json").read_text(encoding="utf-8"))

    def test_conflicting_policy_is_rejected(self):
        self.data["actions"][0]["policy"] = "approval_required"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            Scenario.from_dict(self.data)

    def test_unknown_action_cannot_declare_itself_allowed(self):
        self.data["actions"][0]["id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            Scenario.from_dict(self.data)

    def test_invalid_costs_are_rejected(self):
        for cost in (-1, None, True, "2", math.inf, math.nan):
            data = copy.deepcopy(self.data)
            data["actions"][0]["cost"] = cost
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                Scenario.from_dict(data)

    def test_zero_cost_is_valid(self):
        self.data["actions"][0]["cost"] = 0
        self.assertEqual(plan(Scenario.from_dict(self.data))["total_cost"], 0)

    def test_duplicate_action_ids_are_rejected(self):
        self.data["actions"].append(self.data["actions"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            Scenario.from_dict(self.data)

    def test_malformed_schema_is_rejected(self):
        for key, value in (("initial_evidence", "text"), ("required_evidence", [1]), ("actions", {}), ("scenario_id", "")):
            data = copy.deepcopy(self.data)
            data[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                Scenario.from_dict(data)

    def test_malformed_action_is_rejected(self):
        for key, value in (("id", ""), ("policy", "invalid"), ("preconditions", None), ("effects", [""])):
            data = copy.deepcopy(self.data)
            data["actions"][0][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                Scenario.from_dict(data)


if __name__ == "__main__":
    unittest.main()
