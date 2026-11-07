"""Decide whether an external reply may be sent automatically.

The gate does not send mail and does not trust the model. A passing rubric is
one required input. Send authority is an explicit per-role, per-intent rule
that an owner stores outside the agent. The first-reply intent used by one
observed Hello exception cannot be widened to excluded audiences.
"""

from __future__ import annotations

import re

from reference.binding import addr_spec, approval_problem, envelope_problem, payload_sha256, template_problem
from reference.outbound import delivery_blockers
from reference.reservation import ReservationLedger
from reference.retry import attempt_allowed
from reference.send_ready import rendered_failures
from reference.suppression import SuppressionLog, recipients_suppressed

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
        "null_reverse_path",
        "kill_switch_global",
        "kill_switch_role",
    }
)

# A person may release these outcomes by approving the exact outbound bytes.
# Kill-switch and inbound hard stops are absent on purpose.
HUMAN_CAN_RELEASE = frozenset(
    {
        "role_requires_human",
        "rule_disabled",
        "no_matching_rule",
        "rubric_not_passed",
        "audience_excluded",
        "audience_not_authorized",
        "follow_up",
        "attachment_present",
        "dmarc_not_passing",
        "destination_not_authenticated",
        "reply_to_misaligned",
        "header_from_unauthenticated",
        "freeform_body",
        "mailing_list",
        "recipient_count",
        "prohibited_category",
        "confidence_below_threshold",
        "template_not_allowed",
        "mode_not_template_only",
        "rate_limited",
        "rate_state_unavailable",
        "rule_audiences_too_wide",
        "rule_missing_follow_up_deny",
        "sender_not_in_rule",
        "rule_incomplete",
        "spam",
    }
)

_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")

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
    "header_from",
    "envelope_mail_from",
    "reply_to",
    "auto_reply_destination",
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
        return _decision(STOP, ["policy_missing"])
    if kill.get("global") is not False:
        return _decision(STOP, ["kill_switch_global"])
    if _null_reverse_path(request.get("envelope_mail_from")):
        return _decision(STOP, ["null_reverse_path"])
    if policy.get("default_outbound_mode") != "human_approval":
        return _decision(STOP, ["policy_default_not_human"])
    if auto.get("require_rubric_pass") is not True:
        return _decision(STOP, ["policy_rubric_gate_disabled"])
    if auto.get("require_explicit_authorization") is not True:
        return _decision(STOP, ["policy_explicit_auth_disabled"])
    if auto.get("allow_freeform") is True:
        return _decision(STOP, ["freeform_not_permitted"])

    invalid = _validate_request(request)
    if invalid:
        return _decision(HUMAN, [invalid])

    role = request["role"]
    role_kills = kill.get("roles")
    if role_kills is None:
        role_kills = {}
    if not isinstance(role_kills, dict):
        return _decision(STOP, ["policy_missing"])
    if role_kills.get(role) is True:
        return _decision(STOP, ["kill_switch_role"])

    human_only = auto.get("human_only_roles")
    if not isinstance(human_only, list) or any(not isinstance(item, str) for item in human_only):
        return _decision(STOP, ["policy_missing"])
    if role in human_only:
        return _decision(HUMAN, ["role_requires_human"])

    if request["freeform_body"] is True:
        return _decision(HUMAN, ["freeform_body"])
    if request["sender_is_mailing_list"] is True:
        return _decision(HUMAN, ["mailing_list"])
    if request["reply_recipient_count"] != 1:
        return _decision(HUMAN, ["recipient_count"])
    destination_problem = _destination_problem(request)
    if destination_problem == "null_reverse_path":
        return _decision(STOP, ["null_reverse_path"])
    if destination_problem:
        return _decision(HUMAN, [destination_problem])
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
        return _decision(STOP, ["policy_missing"])
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

    idempotency_key = request.get("idempotency_key")
    if not isinstance(idempotency_key, str) or _IDEMPOTENCY.fullmatch(idempotency_key) is None:
        return _decision(STOP, ["idempotency_key_missing"])
    try:
        authorized_from = addr_spec(rule.get("from_address"))
    except (TypeError, ValueError):
        return _decision(HUMAN, ["sender_not_in_rule"])
    version = rule.get("template_version")
    if not isinstance(version, str) or not version or any(char.isspace() for char in version):
        return _decision(HUMAN, ["rule_incomplete"])
    try:
        authorized_to = [addr_spec(request["auto_reply_destination"])]
    except (TypeError, ValueError):
        return _decision(HUMAN, ["destination_not_authenticated"])
    return _decision(
        SEND,
        ["explicit_rule_and_rubric"],
        request["template_id"],
        authorized={
            "authorized_from": authorized_from,
            "authorized_to": authorized_to,
            "authorized_cc": [],
            "authorized_bcc": [],
            "authorized_reply_to": [],
            "template_version": version,
        },
        send_key="auto:" + idempotency_key,
    )


def delivery_allowed(
    *,
    request,
    policy,
    rate_state,
    message,
    ledger=None,
    approval=None,
    template_text=None,
    template_html=None,
    template_subject=None,
    template_version=None,
    template_variables=None,
    allow_hosts=(),
    required_assets=(),
    suppression_log=None,
    sender_allowlist=None,
    verified_domain=None,
    postal_address=None,
    send_attempt=1,
):
    """Authorize one handoff of this exact message.

    The decision is recomputed here. A caller-supplied action or recipient
    list is not an input. `ledger` must be a ReservationLedger. Omitting it
    refuses the send. `suppression_log` is read again for this attempt,
    including a later retry that uses a new approval id. Omitting the log
    refuses the send. A True result means this caller won `handoff_started`
    and may call the provider once. A crash after that, or an unknown
    provider result, stays on that key and does not become another send.
    """

    if not isinstance(ledger, ReservationLedger):
        return False
    if not isinstance(suppression_log, SuppressionLog):
        return False
    if not attempt_allowed(policy, send_attempt):
        return False
    try:
        if recipients_suppressed(suppression_log, message):
            return False
    except (TypeError, ValueError):
        return False
    decision = decide(request, policy, rate_state)
    reasons = decision.get("reasons")
    if not isinstance(reasons, list) or HARD_STOP_REASONS.intersection(reasons):
        return False
    if rendered_failures(message, allow_hosts=allow_hosts, required_assets=required_assets):
        return False
    action = decision.get("action")
    if delivery_blockers(
        message,
        action=action,
        sender_allowlist=sender_allowlist,
        verified_domain=verified_domain,
        postal_address=postal_address,
    ):
        return False
    try:
        digest = payload_sha256(message)
    except (TypeError, ValueError):
        return False
    if action == SEND:
        if reasons != ["explicit_rule_and_rubric"] or not decision.get("template_id"):
            return False
        if envelope_problem(decision, message) is not None:
            return False
        if decision.get("template_version") != template_version:
            return False
        if (
            template_problem(
                message,
                text_source=template_text,
                html_source=template_html,
                subject=template_subject,
                version=template_version,
                variables=template_variables,
                template_id=decision["template_id"],
            )
            is not None
        ):
            return False
        if not _recipients_still_clear(suppression_log, message):
            return False
        return ledger.claim_handoff(decision.get("send_key"), digest)
    if not (len(reasons) == 1 and reasons[0] in HUMAN_CAN_RELEASE):
        return False
    if action == HUMAN or (action == STOP and reasons == ["spam"]):
        if approval_problem(message, approval) is not None:
            return False
        if approval.get("payload_sha256") != digest:
            return False
        if not _recipients_still_clear(suppression_log, message):
            return False
        return ledger.claim_handoff(approval.get("approval_id"), digest)
    return False


def _recipients_still_clear(suppression_log, message):
    try:
        return not recipients_suppressed(suppression_log, message)
    except (TypeError, ValueError):
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
        ("per_recipient_address_per_day", "recipient_sent_last_day"),
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


def _null_reverse_path(value):
    return isinstance(value, str) and value.strip().lower() in {"", "<>"}


def _destination_problem(request):
    """Auto-reply only to the single DMARC-authenticated header From address.

    DMARC evaluates the header From domain. The envelope MAIL FROM can be a
    different bounce domain, or `<>` for a delivery status. Neither of those
    is the reply destination. A Reply-To that disagrees with header From is
    not used automatically.
    """

    if _null_reverse_path(request.get("envelope_mail_from")):
        return "null_reverse_path"
    header_from = request.get("header_from")
    if not isinstance(header_from, list) or len(header_from) != 1:
        return "header_from_unauthenticated"
    try:
        authenticated = _addr(header_from[0])
        destination = _addr(request.get("auto_reply_destination"))
    except ValueError:
        return "header_from_unauthenticated"
    if destination != authenticated:
        return "destination_not_authenticated"
    reply_to = request.get("reply_to")
    if not isinstance(reply_to, list):
        return "header_from_unauthenticated"
    if reply_to:
        try:
            reply_addrs = [_addr(item) for item in reply_to]
        except ValueError:
            return "reply_to_misaligned"
        if reply_addrs != [authenticated]:
            return "reply_to_misaligned"
    if request.get("dmarc_pass") is not True:
        return "dmarc_not_passing"
    return None


def _addr(value):
    return addr_spec(value)


def _validate_request(request):
    for key in REQUIRED_KEYS:
        if key not in request:
            return "request_invalid"
    for key in BOOL_KEYS:
        if not isinstance(request[key], bool):
            return "request_invalid"
    if not isinstance(request["header_from"], list) or not isinstance(request["reply_to"], list):
        return "request_invalid"
    if not isinstance(request["envelope_mail_from"], str) or not isinstance(request["auto_reply_destination"], str):
        return "request_invalid"
    if any(not isinstance(item, str) for item in request["header_from"] + request["reply_to"]):
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


def _decision(action, reasons, template_id=None, authorized=None, send_key=None):
    result = {"action": action, "reasons": list(reasons), "template_id": template_id}
    if authorized:
        result.update(authorized)
    if send_key:
        result["send_key"] = send_key
    return result
