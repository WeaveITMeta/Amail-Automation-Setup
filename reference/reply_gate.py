"""Decide whether an external reply may be sent automatically.

The gate does not send mail and does not trust the model. A passing rubric is
one required input. Send authority is an explicit per-role, per-intent rule
that an owner stores outside the agent. The first-reply intent used by one
observed Hello exception cannot be widened to excluded audiences.
"""

from __future__ import annotations

import re

HUMAN = "human_review"
SEND = "template_send"
STOP = "do_not_send"

FIRST_REPLY_INTENT = "first_reply_new_inquiry"
FIRST_REPLY_AUDIENCES = frozenset({"new_inquiry", "routing"})
EXCLUDED_AUDIENCES = frozenset(
    {
        "partner",
        "press",
        "vendor",
        "personal",
        "legal",
        "financial",
        "government",
        "spam",
        "no_reply",
        "follow_up",
    }
)

HARD_STOP_REASONS = frozenset(
    {
        "duplicate_delivery",
        "quarantine_virus",
        "test_or_notice",
        "suppression_or_opt_out",
        "noreply_sender",
    }
)

REQUIRED_KEYS = (
    "role",
    "intent",
    "audience",
    "prohibited_categories",
    "rubric_pass",
    "confidence",
    "template_id",
    "sender_is_mailing_list",
    "sender_is_noreply",
    "reply_recipient_count",
    "dmarc_pass",
    "has_attachment",
    "freeform_body",
    "is_follow_up",
    "thread_already_replied",
    "is_test_or_notice",
    "suppression_or_opt_out",
    "already_sent",
    "already_pending_send",
    "virus_verdict_fail",
    "spam_verdict_fail",
)

BOOL_KEYS = (
    "rubric_pass",
    "sender_is_mailing_list",
    "sender_is_noreply",
    "dmarc_pass",
    "has_attachment",
    "freeform_body",
    "is_follow_up",
    "thread_already_replied",
    "is_test_or_notice",
    "suppression_or_opt_out",
    "already_sent",
    "already_pending_send",
    "virus_verdict_fail",
    "spam_verdict_fail",
)

_ROLE = re.compile(r"^[a-z0-9-]+$")
_TOKEN = re.compile(r"^[a-z0-9_]+$")
_TEMPLATE = re.compile(r"^[a-z0-9-]+$")


def decide(request, policy, rate_state):
    """Return action, reasons, and template_id.

    Actions are human_review, template_send, and do_not_send.
    Extra fields such as force_send are ignored.
    """

    if not isinstance(policy, dict) or not isinstance(request, dict):
        return _decision(HUMAN, ["policy_missing" if not isinstance(policy, dict) else "request_invalid"])

    if request.get("already_sent") is True or request.get("already_pending_send") is True:
        return _decision(STOP, ["duplicate_delivery"])
    if request.get("virus_verdict_fail") is True:
        return _decision(STOP, ["quarantine_virus"])
    if request.get("is_test_or_notice") is True:
        return _decision(STOP, ["test_or_notice"])
    if request.get("suppression_or_opt_out") is True:
        return _decision(STOP, ["suppression_or_opt_out"])
    if request.get("spam_verdict_fail") is True or request.get("audience") == "spam":
        return _decision(STOP, ["spam"])
    if request.get("sender_is_noreply") is True or request.get("audience") == "no_reply":
        return _decision(STOP, ["noreply_sender"])

    auto = policy.get("auto_reply")
    kill = policy.get("kill_switch")
    if not isinstance(auto, dict) or not isinstance(kill, dict):
        return _decision(HUMAN, ["policy_missing"])
    if kill.get("global") is not False:
        return _decision(HUMAN, ["kill_switch_global"])
    if policy.get("default_outbound_mode") != "human_approval":
        return _decision(HUMAN, ["policy_default_not_human"])
    if auto.get("require_rubric_pass") is not True:
        return _decision(HUMAN, ["policy_rubric_gate_disabled"])
    if auto.get("require_explicit_authorization") is not True:
        return _decision(HUMAN, ["policy_explicit_auth_disabled"])
    if auto.get("allow_freeform") is True:
        return _decision(HUMAN, ["freeform_not_permitted"])

    invalid = _validate_request(request)
    if invalid:
        return _decision(HUMAN, [invalid])

    role = request["role"]
    role_kills = kill.get("roles")
    if role_kills is None:
        role_kills = {}
    if not isinstance(role_kills, dict):
        return _decision(HUMAN, ["policy_missing"])
    if role_kills.get(role) is True:
        return _decision(HUMAN, ["kill_switch_role"])

    human_only = auto.get("human_only_roles")
    if not isinstance(human_only, list) or any(not isinstance(item, str) for item in human_only):
        return _decision(HUMAN, ["policy_missing"])
    if role in human_only:
        return _decision(HUMAN, ["role_requires_human"])

    if request["freeform_body"] is True:
        return _decision(HUMAN, ["freeform_body"])
    if request["sender_is_mailing_list"] is True:
        return _decision(HUMAN, ["mailing_list"])
    if request["reply_recipient_count"] != 1:
        return _decision(HUMAN, ["recipient_count"])
    if request["dmarc_pass"] is not True:
        return _decision(HUMAN, ["dmarc_not_passing"])
    if request["has_attachment"] is True:
        return _decision(HUMAN, ["attachment_present"])
    if request["prohibited_categories"]:
        return _decision(HUMAN, ["prohibited_category"])
    if request["is_follow_up"] is True or request["thread_already_replied"] is True:
        return _decision(HUMAN, ["follow_up"])
    if request["audience"] in EXCLUDED_AUDIENCES:
        return _decision(HUMAN, ["audience_excluded"])

    intent = request["intent"]
    if intent == FIRST_REPLY_INTENT and request["audience"] not in FIRST_REPLY_AUDIENCES:
        return _decision(HUMAN, ["audience_not_authorized"])

    rules = auto.get("rules")
    if not isinstance(rules, list):
        return _decision(HUMAN, ["policy_missing"])
    rule = _matching_rule(rules, role, intent)
    if rule is None:
        return _decision(HUMAN, ["no_matching_rule"])
    if rule.get("enabled") is not True:
        return _decision(HUMAN, ["rule_disabled"])
    if rule.get("mode") != "template_only":
        return _decision(HUMAN, ["mode_not_template_only"])

    if intent == FIRST_REPLY_INTENT:
        allowed = rule.get("allow_audiences")
        if not isinstance(allowed, list) or not set(allowed) <= FIRST_REPLY_AUDIENCES:
            return _decision(HUMAN, ["rule_audiences_too_wide"])
        if request["audience"] not in set(allowed):
            return _decision(HUMAN, ["audience_not_authorized"])
        if rule.get("deny_if_follow_up") is not True:
            return _decision(HUMAN, ["rule_missing_follow_up_deny"])

    if request["rubric_pass"] is not True:
        return _decision(HUMAN, ["rubric_not_passed"])

    minimum = auto.get("min_confidence")
    confidence = request["confidence"]
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
        return _decision(HUMAN, ["policy_missing"])
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return _decision(HUMAN, ["request_invalid"])
    if confidence != confidence or not 0 <= float(confidence) <= 1:
        return _decision(HUMAN, ["request_invalid"])
    if float(confidence) < float(minimum):
        return _decision(HUMAN, ["confidence_below_threshold"])

    templates = rule.get("templates")
    if not isinstance(templates, list) or request["template_id"] not in templates:
        return _decision(HUMAN, ["template_not_allowed"])

    limited = _rate_limit(auto.get("rate_limits"), rate_state)
    if limited:
        return _decision(HUMAN, [limited])

    return _decision(SEND, ["explicit_rule_and_rubric"], request["template_id"])


def human_send_allowed(approval):
    """A person approved this exact rendered draft. Agents cannot approve."""

    if not isinstance(approval, dict):
        return False
    required = ("permission", "decision", "approver", "draft_id", "rendered_sha256")
    if any(key not in approval for key in required):
        return False
    if approval["permission"] != "send" or approval["decision"] != "approved":
        return False
    if approval["approver"] != "person":
        return False
    if not isinstance(approval["draft_id"], str) or not approval["draft_id"]:
        return False
    digest = approval["rendered_sha256"]
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) < 12:
        return False
    return True


def delivery_allowed(*, decision, approval, rendered_ok):
    """Combine the gate, a human approval, and rendered-message checks.

    Hard stops (duplicate, virus, test/notice, suppression, no-reply) stay
    blocked when a person approval is present. Spam blocks the agent and can
    still be released by a person. template_send does not need a person, and
    it still requires the rendered checks.
    """

    if not isinstance(decision, dict) or rendered_ok is not True:
        return False
    reasons = decision.get("reasons")
    if not isinstance(reasons, list):
        return False
    if HARD_STOP_REASONS.intersection(reasons):
        return False
    action = decision.get("action")
    if action == SEND:
        return reasons == ["explicit_rule_and_rubric"] and bool(decision.get("template_id"))
    if action == HUMAN and human_send_allowed(approval):
        return True
    if action == STOP and reasons == ["spam"] and human_send_allowed(approval):
        return True
    return False


def _matching_rule(rules, role, intent):
    matches = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("role") == role and rule.get("intent") == intent
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _rate_limit(limits, rate_state):
    if not isinstance(limits, dict) or not isinstance(rate_state, dict):
        return "rate_state_unavailable"
    pairs = (
        ("per_role_per_hour", "role_sent_last_hour"),
        ("per_sender_per_day", "sender_sent_last_day"),
        ("per_recipient_address_per_hour", "recipient_sent_last_hour"),
    )
    for limit_key, state_key in pairs:
        cap = limits.get(limit_key)
        used = rate_state.get(state_key)
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
            return "rate_state_unavailable"
        if isinstance(used, bool) or not isinstance(used, int) or used < 0:
            return "rate_state_unavailable"
        if used >= cap:
            return "rate_limited"
    return None


def _validate_request(request):
    for key in REQUIRED_KEYS:
        if key not in request:
            return "request_invalid"
    for key in BOOL_KEYS:
        if not isinstance(request[key], bool):
            return "request_invalid"
    categories = request["prohibited_categories"]
    if not isinstance(categories, list) or any(not isinstance(item, str) or not item for item in categories):
        return "request_invalid"
    if not _ROLE.fullmatch(request["role"]):
        return "request_invalid"
    if not _TOKEN.fullmatch(request["intent"]) or not _TOKEN.fullmatch(request["audience"]):
        return "request_invalid"
    if not _TEMPLATE.fullmatch(request["template_id"]):
        return "request_invalid"
    count = request["reply_recipient_count"]
    if isinstance(count, bool) or not isinstance(count, int):
        return "request_invalid"
    confidence = request["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return "request_invalid"
    return None


def _decision(action, reasons, template_id=None):
    return {"action": action, "reasons": list(reasons), "template_id": template_id}
