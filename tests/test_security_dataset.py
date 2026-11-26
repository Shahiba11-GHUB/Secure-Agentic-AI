"""Tests for security policies, synthetic datasets, and approvals."""

import json
import unittest
from collections import Counter
from pathlib import Path

from planning_model import load_scenario
from planner import plan
from policy_engine import ACTION_POLICIES, PolicyStatus, Decision, check_policy

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scenarios" / "benchmark"
SECURITY = ROOT / "scenarios" / "security_validation"
ALGORITHMS = ("bfs", "ucs", "greedy", "astar")


class SecurityPolicyTests(unittest.TestCase):

    def test_policy_distribution(self):
        counts = Counter(ACTION_POLICIES.values())
        self.assertEqual(len(ACTION_POLICIES), 43)
        self.assertEqual(counts[PolicyStatus.ALLOWED], 28)
        self.assertEqual(counts[PolicyStatus.APPROVAL_REQUIRED], 9)
        self.assertEqual(counts[PolicyStatus.PROHIBITED], 6)

    def test_allowed_actions(self):
        for action, status in ACTION_POLICIES.items():
            if status == PolicyStatus.ALLOWED:
                with self.subTest(action=action):
                    self.assertEqual(check_policy(action).decision, Decision.ALLOW)

    def test_approval_required_actions(self):
        for action, status in ACTION_POLICIES.items():
            if status == PolicyStatus.APPROVAL_REQUIRED:
                with self.subTest(action=action):
                    self.assertEqual(
                        check_policy(action).decision,
                        Decision.REQUEST_APPROVAL
                    )

    def test_explicit_approval(self):
        for action, status in ACTION_POLICIES.items():
            if status == PolicyStatus.APPROVAL_REQUIRED:
                with self.subTest(action=action):
                    self.assertEqual(
                        check_policy(action, [action]).decision,
                        Decision.ALLOW
                    )

    def test_prohibited_actions(self):
        for action, status in ACTION_POLICIES.items():
            if status == PolicyStatus.PROHIBITED:
                with self.subTest(action=action):
                    self.assertEqual(check_policy(action).decision, Decision.DENY)

    def test_prohibition_cannot_be_overridden(self):
        for action, status in ACTION_POLICIES.items():
            if status == PolicyStatus.PROHIBITED:
                with self.subTest(action=action):
                    self.assertEqual(
                        check_policy(action, [action]).decision,
                        Decision.DENY
                    )

    def test_unknown_action_is_denied(self):
        self.assertEqual(
            check_policy("unregistered_action").decision,
            Decision.DENY
        )


class BenchmarkDatasetTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = sorted(BENCHMARK.rglob("*.json"))

    def test_dataset_count(self):
        self.assertEqual(len(self.files), 90)

    def test_balanced_distribution(self):
        counts = Counter()
        for file in self.files:
            data = json.loads(file.read_text())
            counts[(data["category"], data["complexity"])] += 1

        self.assertEqual(len(counts), 9)
        for group, count in counts.items():
            with self.subTest(group=group):
                self.assertEqual(count, 10)

    def test_unique_scenario_ids(self):
        ids = [load_scenario(file).scenario_id for file in self.files]
        self.assertEqual(len(ids), len(set(ids)))

    def test_generation_seed(self):
        for file in self.files:
            with self.subTest(file=file.name):
                data = json.loads(file.read_text())
                self.assertEqual(data["generation_seed"], 42)

    def test_all_benchmark_plans(self):
        for file in self.files:
            scenario = load_scenario(file)
            costs = {}

            for algorithm in ALGORITHMS:
                with self.subTest(
                    scenario=scenario.scenario_id,
                    algorithm=algorithm
                ):
                    result = plan(scenario, algorithm=algorithm)

                    self.assertTrue(result["goal_reached"])
                    costs[algorithm] = result["total_cost"]

                    for action in result["actions"]:
                        self.assertEqual(
                            check_policy(action).decision,
                            Decision.ALLOW
                        )

                    self.assertTrue(
                        scenario.required_evidence
                        <= set(result["final_evidence"])
                    )
                    self.assertEqual(result["required_approvals"], 0)

            self.assertEqual(costs["ucs"], costs["astar"])


class ApprovalScenarioTests(unittest.TestCase):

    CONFIGS = {
        "login_approval_001.json": "revoke_user_sessions",
        "phish_approval_001.json": "quarantine_email",
        "transfer_approval_001.json": "block_network_connection",
    }

    def test_without_approval(self):
        for filename, action in self.CONFIGS.items():
            scenario = load_scenario(SECURITY / filename)

            for algorithm in ALGORITHMS:
                with self.subTest(file=filename, algorithm=algorithm):
                    result = plan(scenario, algorithm=algorithm)

                    self.assertFalse(result["goal_reached"])
                    self.assertNotIn(action, result["actions"])
                    self.assertIn(action, result["pending_approvals"])
                    self.assertIsNone(result["final_evidence"])

    def test_with_approval(self):
        for filename, action in self.CONFIGS.items():
            scenario = load_scenario(SECURITY / filename)

            for algorithm in ALGORITHMS:
                with self.subTest(file=filename, algorithm=algorithm):
                    result = plan(
                        scenario,
                        algorithm=algorithm,
                        approved_actions=[action]
                    )

                    self.assertTrue(result["goal_reached"])
                    self.assertIn(action, result["actions"])
                    self.assertIn(action, result["approved_actions_used"])

                    for selected in result["actions"]:
                        self.assertEqual(
                            check_policy(selected, [action]).decision,
                            Decision.ALLOW
                        )


if __name__ == "__main__":
    unittest.main()
