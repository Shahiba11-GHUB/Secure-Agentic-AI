import unittest
from policy_engine import check_policy, Decision


class PolicyEngineTests(unittest.TestCase):
    def test_allowed_read_only_action(self):
        self.assertEqual(check_policy("check_login_history").decision, Decision.ALLOW)

    def test_approval_required_without_approval(self):
        self.assertEqual(check_policy("disable_account").decision, Decision.REQUEST_APPROVAL)

    def test_approval_granted(self):
        self.assertEqual(check_policy("disable_account", {"disable_account"}).decision, Decision.ALLOW)

    def test_approval_does_not_override_prohibition(self):
        self.assertEqual(check_policy("delete_logs", {"delete_logs"}).decision, Decision.DENY)

    def test_unknown_action_denied(self):
        self.assertEqual(check_policy("export_sensitive_data").decision, Decision.DENY)


if __name__ == "__main__":
    unittest.main()
