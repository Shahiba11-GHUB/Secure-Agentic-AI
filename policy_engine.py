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

    # ==========================================
    # 1. Suspicious Login Investigation
    # ==========================================

    "check_login_history": PolicyStatus.ALLOWED,
    "check_ip_reputation": PolicyStatus.ALLOWED,
    "review_device_status": PolicyStatus.ALLOWED,
    "scan_device": PolicyStatus.ALLOWED,
    "confirm_login": PolicyStatus.ALLOWED,
    "check_mfa_activity": PolicyStatus.ALLOWED,
    "review_account_permissions": PolicyStatus.ALLOWED,
    "review_session_activity": PolicyStatus.ALLOWED,
    "review_identity_alert": PolicyStatus.ALLOWED,
    "correlate_identity_evidence": PolicyStatus.ALLOWED,

    "force_password_reset": PolicyStatus.APPROVAL_REQUIRED,
    "disable_account": PolicyStatus.APPROVAL_REQUIRED,
    "revoke_user_sessions": PolicyStatus.APPROVAL_REQUIRED,

    # ==========================================
    # 2. Phishing Email Investigation
    # ==========================================

    "check_email_headers": PolicyStatus.ALLOWED,
    "verify_sender_domain": PolicyStatus.ALLOWED,
    "check_url_reputation": PolicyStatus.ALLOWED,
    "review_attachment_metadata": PolicyStatus.ALLOWED,
    "analyze_attachment_sandbox": PolicyStatus.ALLOWED,
    "check_affected_recipients": PolicyStatus.ALLOWED,
    "review_email_gateway_logs": PolicyStatus.ALLOWED,
    "review_email_security_alert": PolicyStatus.ALLOWED,
    "correlate_email_evidence": PolicyStatus.ALLOWED,

    "quarantine_email": PolicyStatus.APPROVAL_REQUIRED,
    "block_sender_domain": PolicyStatus.APPROVAL_REQUIRED,
    "block_malicious_url": PolicyStatus.APPROVAL_REQUIRED,

    # ==========================================
    # 3. Unusual Data Transfer Investigation
    # ==========================================

    "check_network_logs": PolicyStatus.ALLOWED,
    "review_destination_ip": PolicyStatus.ALLOWED,
    "check_user_activity": PolicyStatus.ALLOWED,
    "review_data_classification": PolicyStatus.ALLOWED,
    "review_transfer_volume": PolicyStatus.ALLOWED,
    "check_dlp_alerts": PolicyStatus.ALLOWED,
    "review_file_access_logs": PolicyStatus.ALLOWED,
    "review_transfer_alert": PolicyStatus.ALLOWED,
    "correlate_transfer_evidence": PolicyStatus.ALLOWED,

    "block_network_connection": PolicyStatus.APPROVAL_REQUIRED,
    "isolate_endpoint": PolicyStatus.APPROVAL_REQUIRED,
    "suspend_file_transfer": PolicyStatus.APPROVAL_REQUIRED,

    # ==========================================
    # 4. Prohibited Actions
    # ==========================================

    "delete_logs": PolicyStatus.PROHIBITED,
    "wipe_device": PolicyStatus.PROHIBITED,
    "delete_investigation_evidence": PolicyStatus.PROHIBITED,
    "export_confidential_data": PolicyStatus.PROHIBITED,
    "disable_security_monitoring": PolicyStatus.PROHIBITED,
    "bypass_security_policy": PolicyStatus.PROHIBITED,
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
