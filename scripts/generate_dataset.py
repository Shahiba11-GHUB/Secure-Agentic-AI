"""Generate 90 reproducible synthetic cybersecurity scenarios."""

import copy
import json
import random
from pathlib import Path

from planning_model import Scenario

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scenarios" / "experimental"
OUTPUT = ROOT / "scenarios" / "benchmark"

SEED = 42
rng = random.Random(SEED)

CONFIGS = {
    "suspicious_login": {
        "prefix": "LOGIN",
        "source": "suspicious_login/login_exp_001.json",
        "bundle": "review_identity_alert",
        "correlation": "correlate_identity_evidence",
        "extra": [
            ("check_mfa_activity",
             "login_history_checked",
             "mfa_activity_checked", 2),
            ("review_account_permissions",
             "login_history_checked",
             "account_permissions_reviewed", 2),
            ("review_session_activity",
             "account_permissions_reviewed",
             "session_activity_reviewed", 3),
            ("confirm_login",
             "login_history_checked",
             "user_contacted", 3)
        ]
    },

    "phishing": {
        "prefix": "PHISH",
        "source": "phishing/phish_exp_001.json",
        "bundle": "review_email_security_alert",
        "correlation": "correlate_email_evidence",
        "extra": [
            ("review_attachment_metadata",
             "email_headers_checked",
             "attachment_metadata_reviewed", 2),
            ("analyze_attachment_sandbox",
             "attachment_metadata_reviewed",
             "attachment_analyzed", 3),
            ("check_affected_recipients",
             "sender_domain_verified",
             "recipients_checked", 3),
            ("review_email_gateway_logs",
             "email_headers_checked",
             "gateway_logs_reviewed", 2)
        ]
    },

    "data_transfer": {
        "prefix": "TRANSFER",
        "source": "data_transfer/transfer_exp_001.json",
        "bundle": "review_transfer_alert",
        "correlation": "correlate_transfer_evidence",
        "extra": [
            ("review_transfer_volume",
             "network_logs_checked",
             "transfer_volume_reviewed", 3),
            ("check_user_activity",
             "network_logs_checked",
             "user_activity_checked", 2),
            ("check_dlp_alerts",
             "data_classification_reviewed",
             "dlp_alerts_checked", 3),
            ("review_file_access_logs",
             "user_activity_checked",
             "file_access_reviewed", 3)
        ]
    }
}


def create_action(action_id, cost, preconditions, effects):
    return {
        "id": action_id,
        "cost": cost,
        "policy": "allowed",
        "preconditions": preconditions,
        "effects": effects
    }


def generate():

    rng.seed(SEED)
    total = 0

    levels = {
        "simple": 0,
        "medium": 2,
        "complex": 4
    }

    for category, config in CONFIGS.items():

        template = json.loads(
            (BASE / config["source"]).read_text()
        )

        for level, extra_count in levels.items():

            folder = OUTPUT / category / level
            folder.mkdir(parents=True, exist_ok=True)

            for number in range(1, 11):

                data = copy.deepcopy(template)

                scenario_id = (
                    f'{config["prefix"]}-'
                    f'{level.upper()}-{number:03d}'
                )

                data["scenario_id"] = scenario_id
                data["scenario_name"] = scenario_id
                data["category"] = category
                data["complexity"] = level
                data["generation_seed"] = SEED
                data["simulation_only"] = True

                actions = {
                    action["id"]: action
                    for action in data["actions"]
                }

                base_goals = list(data["required_evidence"])

                # Add more evidence and dependencies.
                selected = config["extra"][:extra_count]

                for action_id, prerequisite, effect, cost in selected:

                    actions[action_id] = create_action(
                        action_id,
                        cost,
                        [prerequisite],
                        [effect]
                    )

                    data["required_evidence"].append(effect)

                # Vary the investigation costs.
                for action_id, action in actions.items():

                    if (
                        action["policy"] == "allowed"
                        and action_id != config["bundle"]
                    ):
                        action["cost"] = max(
                            1,
                            action["cost"] + rng.randint(-1, 2)
                        )

                # Calculate the separate basic evidence costs.
                direct_cost = sum(
                    action["cost"]
                    for action_id, action in actions.items()
                    if action_id != config["bundle"]
                    and action["policy"] == "allowed"
                    and any(
                        fact in base_goals
                        for fact in action["effects"]
                    )
                )

                # Avoid favoring one algorithm in every case.
                if number <= 3:
                    bundle_cost = max(1, direct_cost - 1)
                    data["cost_relationship"] = "bundle_cheaper"

                elif number <= 6:
                    bundle_cost = direct_cost
                    data["cost_relationship"] = "equal_cost"

                else:
                    bundle_cost = direct_cost + rng.randint(2, 5)
                    data["cost_relationship"] = "bundle_expensive"

                actions[config["bundle"]]["cost"] = bundle_cost

                # Add a consolidated correlation alternative
                # for medium and complex investigations.
                if selected:

                    effects = [
                        item[2] for item in selected
                    ]

                    correlation_cost = rng.randint(3, 10)

                    actions[config["correlation"]] = create_action(
                        config["correlation"],
                        correlation_cost,
                        base_goals,
                        effects
                    )

                data["actions"] = list(actions.values())

                data["goal"] = (
                    "Collect all required simulated evidence "
                    "for analyst review."
                )

                data["description"] = (
                    f"Synthetic {category} investigation "
                    f"with {level} planning complexity."
                )

                # Validate using Tanuj's existing model.
                Scenario.from_dict(data)

                destination = folder / (
                    scenario_id.lower() + ".json"
                )

                destination.write_text(
                    json.dumps(data, indent=2) + "\n",
                    encoding="utf-8"
                )

                total += 1

            print(category, "|", level, "| 10 generated")

    print("\nGeneration seed:", SEED)
    print("Total scenarios generated:", total)
    print("Output:", OUTPUT)

    assert total == 90


if __name__ == "__main__":
    generate()
