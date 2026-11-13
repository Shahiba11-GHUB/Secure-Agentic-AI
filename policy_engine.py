"""Policy decisions for simulated security-investigation actions.

This module is deliberately independent of any particular search algorithm.
A plan recommendation is NOT the same as executing an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Collection, Mapping


class PolicyStatus(str, Enum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"
    PROHIBITED = "prohibited"


class Decision(str, Enum):
    ALLOW = "allow"
    REQUEST_APPROVAL = "request_approval"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyResult:
    action_id: str
    decision: Decision
    reason: str


# Default deny: unfamiliar actions are never silently allowed.
ACTION_POLICIES: Mapping[str, PolicyStatus] = {
    "check_login_history": PolicyStatus.ALLOWED,
    "check_ip_reputation": PolicyStatus.ALLOWED,
    "review_device_status": PolicyStatus.ALLOWED,
    "scan_device": PolicyStatus.ALLOWED,
    "confirm_login": PolicyStatus.ALLOWED,
    "force_password_reset": PolicyStatus.APPROVAL_REQUIRED,
    "disable_account": PolicyStatus.APPROVAL_REQUIRED,
    "delete_logs": PolicyStatus.PROHIBITED,
    "wipe_device": PolicyStatus.PROHIBITED,
}


def check_policy(
    action_id: str,
    approved_actions: Collection[str] = (),
) -> PolicyResult:
    """Classify a proposed action without performing it.

    Approval is modeled by an explicit list of approved action IDs. A real
    deployment would also verify the approval's identity, scope, and validity.
    """
    status = ACTION_POLICIES.get(action_id, PolicyStatus.PROHIBITED)
    if status == PolicyStatus.PROHIBITED:
        return PolicyResult(action_id, Decision.DENY, "Action is prohibited or unknown")
    if status == PolicyStatus.APPROVAL_REQUIRED and action_id not in approved_actions:
        return PolicyResult(action_id, Decision.REQUEST_APPROVAL, "Human approval required before execution")
    if status == PolicyStatus.APPROVAL_REQUIRED:
        return PolicyResult(action_id, Decision.ALLOW, "Human approval recorded")
    return PolicyResult(action_id, Decision.ALLOW, "Read-only or otherwise pre-approved investigation action")


if __name__ == "__main__":
    for action in ("check_login_history", "disable_account", "delete_logs", "unknown_action"):
        result = check_policy(action)
        print(f"{result.action_id}: {result.decision.value} — {result.reason}")
