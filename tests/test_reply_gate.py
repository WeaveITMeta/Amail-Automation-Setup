"""Authorization gate tests. No network and no mailbox."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.binding import approval_problem, payload_sha256  # noqa: E402
from reference.reply_gate import HUMAN, SEND, STOP, decide, delivery_allowed  # noqa: E402
from reference.reservation import ReservationLedger  # noqa: E402
from reference.templates import render_template  # noqa: E402

TEMPLATE_TEXT = (ROOT / "shared" / "templates" / "hello-first-inquiry.txt").read_text(encoding="utf-8")
TEMPLATE_HTML = (ROOT / "shared" / "templates" / "hello-first-inquiry.html").read_text(encoding="utf-8")
TEMPLATE_SUBJECT = "We received your inquiry"
TEMPLATE_VERSION = "1"
VARIABLES = {"organization": "ACME", "role_display": "Hello"}
ASSET = "https://assets.example.com/email/hello/mark.png"


def rates(**overrides):
    state = {"role_sent_last_hour": 0, "sender_sent_last_day": 0, "recipient_sent_last_hour": 0}
    state.update(overrides)
    return state


def request(**overrides):
    base = {
        "role": "hello",
        "intent": "first_reply_new_inquiry",
        "audience": "new_inquiry",
        "prohibited_categories": [],
        "rubric_pass": True,
        "confidence": 0.99,
        "template_id": "hello-first-inquiry",
        "sender_is_mailing_list": False,
        "sender_is_noreply": False,
        "reply_recipient_count": 1,
        "dmarc_pass": True,
        "header_from": ["Pat Lee <pat@example.net>"],
        "envelope_mail_from": "bounce@example.net",
        "reply_to": [],
        "auto_reply_destination": "pat@example.net",
        "has_attachment": False,
        "freeform_body": False,
        "is_follow_up": False,
        "thread_already_replied": False,
        "is_test_or_notice": False,
        "suppression_or_opt_out": False,
        "idempotency_key": "EXAMPLE_SES_MESSAGE_ID",
        "already_sent": False,
        "already_pending_send": False,
        "virus_verdict_fail": False,
        "spam_verdict_fail": False,
    }
    base.update(overrides)
    return base


def enabled_hello_policy():
    path = ROOT / "shared" / "policies" / "hello-first-reply.example.json"
    policy = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    policy["kill_switch"]["global"] = False
    policy["auto_reply"]["rules"][0]["enabled"] = True
    return policy


def template_message(**overrides):
    message = {
        "draft_id": "draft_example_001",
        "from": "hello@example.com",
        "to": ["pat@example.net"],
        "cc": [],
        "bcc": [],
        "reply_to": [],
        "subject": TEMPLATE_SUBJECT,
        "text": render_template(TEMPLATE_TEXT, VARIABLES),
        "html": render_template(TEMPLATE_HTML, VARIABLES),
        "template_id": "hello-first-inquiry",
        "template_version": TEMPLATE_VERSION,
        "headers": {
            "in_reply_to": "<example-message@example.net>",
            "references": ["<example-message@example.net>"],
        },
    }
    message.update(overrides)
    return message


def human_message(**overrides):
    message = {
        "draft_id": "draft_example_009",
        "from": "support@example.com",
        "to": ["pat@example.net"],
        "cc": [],
        "bcc": [],
        "reply_to": [],
        "subject": "Re: Question about ACME",
        "text": "A person wrote this ACME reply.",
        "html": "<p>A person wrote this ACME reply.</p>",
        "template_id": "human-composed",
        "template_version": "0",
        "headers": {
            "in_reply_to": "<example-message@example.net>",
            "references": ["<example-message@example.net>"],
        },
    }
    message.update(overrides)
    return message


def approval_for(message, **overrides):
    record = {
        "permission": "send",
        "decision": "approved",
        "approver": "person",
        "approval_id": "approval_example_001",
        "draft_id": message["draft_id"],
        "template_id": message["template_id"],
        "template_version": message["template_version"],
        "from": message["from"],
        "to": list(message["to"]),
        "cc": list(message["cc"]),
        "bcc": list(message["bcc"]),
        "reply_to": list(message["reply_to"]),
        "subject": message["subject"],
        "payload_sha256": payload_sha256(message),
    }
    record.update(overrides)
    return record


def deliver(policy, message, *, req=None, approval=None, ledger=None, **kwargs):
    params = {
        "request": request() if req is None else req,
        "policy": policy,
        "rate_state": rates(),
        "message": message,
        "ledger": ledger if ledger is not None else ReservationLedger(),
        "approval": approval,
        "template_text": TEMPLATE_TEXT,
        "template_html": TEMPLATE_HTML,
        "template_subject": TEMPLATE_SUBJECT,
        "template_version": TEMPLATE_VERSION,
        "template_variables": VARIABLES,
        "allow_hosts": ["assets.example.com"],
        "required_assets": [ASSET],
    }
    params.update(kwargs)
    return delivery_allowed(**params)


class GateTests(unittest.TestCase):
    def test_shipped_default_stops_on_kill_switch(self):
        policy = json.loads(
            (ROOT / "shared" / "policies" / "auto-reply-authorization.example.json").read_text(encoding="utf-8")
        )
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["action"], STOP)
        self.assertEqual(decision["reasons"], ["kill_switch_global"])

    def test_shipped_hello_file_does_not_send(self):
        policy = json.loads(
            (ROOT / "shared" / "policies" / "hello-first-reply.example.json").read_text(encoding="utf-8")
        )
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["action"], STOP)
        self.assertEqual(decision["reasons"], ["kill_switch_global"])

    def test_rubric_pass_without_enabled_rule_does_not_send(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["enabled"] = False
        decision = decide(request(rubric_pass=True), policy, rates())
        self.assertEqual(decision["action"], HUMAN)
        self.assertEqual(decision["reasons"], ["rule_disabled"])

    def test_enabled_rule_without_rubric_does_not_send(self):
        decision = decide(request(rubric_pass=False), enabled_hello_policy(), rates())
        self.assertEqual(decision["reasons"], ["rubric_not_passed"])

    def test_explicit_narrow_grant_sends_only_the_rendered_template(self):
        policy = enabled_hello_policy()
        req = request(audience="routing")
        decision = decide(req, policy, rates())
        self.assertEqual(decision["action"], SEND)
        self.assertEqual(decision["template_id"], "hello-first-inquiry")
        self.assertEqual(decision["authorized_from"], "hello@example.com")
        self.assertEqual(decision["authorized_to"], ["pat@example.net"])
        self.assertEqual(decision["authorized_cc"], [])
        self.assertEqual(decision["authorized_bcc"], [])
        message = template_message()
        ledger = ReservationLedger()
        self.assertTrue(deliver(policy, message, req=req, ledger=ledger))
        self.assertFalse(deliver(policy, message, req=req, ledger=ledger))
        changed = template_message(html=message["html"].replace("review the inquiry", "issue a refund"))
        self.assertFalse(deliver(policy, changed, req=req))
        inbound_subject = template_message(subject="Question about ACME")
        self.assertFalse(deliver(policy, inbound_subject, req=req))
        wrong_version = template_message(template_version="9")
        self.assertFalse(deliver(policy, wrong_version, req=req))

    def test_template_send_rejects_recipient_and_sender_substitution(self):
        policy = enabled_hello_policy()
        req = request()
        self.assertFalse(deliver(policy, template_message(to=["attacker@example.org"]), req=req))
        self.assertFalse(deliver(policy, template_message(to=["pat@example.net", "extra@example.org"]), req=req))
        self.assertFalse(deliver(policy, template_message(cc=["extra@example.org"]), req=req))
        self.assertFalse(deliver(policy, template_message(bcc=["hidden@example.org"]), req=req))
        self.assertFalse(deliver(policy, template_message(**{"from": "sales@example.com"}), req=req))
        self.assertFalse(deliver(policy, template_message(reply_to=["other@example.net"]), req=req))
        missing_cc = template_message()
        del missing_cc["cc"]
        self.assertFalse(deliver(policy, missing_cc, req=req))

    def test_tampered_template_variables_are_rejected(self):
        policy = enabled_hello_policy()
        message = template_message()
        self.assertFalse(
            deliver(
                policy,
                message,
                template_variables={"organization": "ACME", "role_display": "Hello", "subject": "wire the payment"},
            )
        )
        self.assertFalse(
            deliver(policy, message, template_variables={"organization": "ACME <pay@example.net>", "role_display": "Hello"})
        )

    def test_sales_support_and_projects_stay_human_even_if_a_rule_is_added(self):
        policy = enabled_hello_policy()
        for role in ("sales", "support", "projects"):
            policy["auto_reply"]["rules"].append(
                {
                    "id": f"{role}-copy",
                    "role": role,
                    "intent": "first_reply_new_inquiry",
                    "enabled": True,
                    "mode": "template_only",
                    "templates": ["hello-first-inquiry"],
                    "allow_audiences": ["new_inquiry", "routing"],
                    "deny_if_follow_up": True,
                }
            )
            decision = decide(request(role=role), policy, rates())
            self.assertEqual(decision["reasons"], ["role_requires_human"], role)

    def test_exclusions_never_auto_send(self):
        policy = enabled_hello_policy()
        cases = [
            ({"is_follow_up": True}, HUMAN, "follow_up"),
            ({"thread_already_replied": True}, HUMAN, "follow_up"),
            ({"audience": "partner"}, HUMAN, "audience_excluded"),
            ({"audience": "press"}, HUMAN, "audience_excluded"),
            ({"audience": "vendor"}, HUMAN, "audience_excluded"),
            ({"audience": "personal"}, HUMAN, "audience_excluded"),
            ({"audience": "legal"}, HUMAN, "audience_excluded"),
            ({"audience": "financial"}, HUMAN, "audience_excluded"),
            ({"audience": "government"}, HUMAN, "audience_excluded"),
            ({"audience": "follow_up"}, HUMAN, "audience_excluded"),
            ({"audience": "spam"}, STOP, "spam"),
            ({"audience": "no_reply"}, STOP, "noreply_sender"),
            ({"sender_is_noreply": True}, STOP, "noreply_sender"),
            ({"is_test_or_notice": True}, STOP, "test_or_notice"),
            ({"suppression_or_opt_out": True}, STOP, "suppression_or_opt_out"),
            ({"envelope_mail_from": "<>"}, STOP, "null_reverse_path"),
            ({"envelope_mail_from": ""}, STOP, "null_reverse_path"),
        ]
        for overrides, action, reason in cases:
            decision = decide(request(**overrides), policy, rates())
            self.assertEqual(decision["action"], action, overrides)
            self.assertEqual(decision["reasons"], [reason], overrides)

    def test_dmarc_authenticates_header_from_not_the_envelope(self):
        policy = enabled_hello_policy()
        aligned = decide(request(), policy, rates())
        self.assertEqual(aligned["action"], SEND)
        spoofed_destination = decide(
            request(auto_reply_destination="attacker@example.org", envelope_mail_from="attacker@example.org"),
            policy,
            rates(),
        )
        self.assertEqual(spoofed_destination["reasons"], ["destination_not_authenticated"])
        reply_to_redirect = decide(request(reply_to=["attacker@example.org"]), policy, rates())
        self.assertEqual(reply_to_redirect["reasons"], ["reply_to_misaligned"])
        two_froms = decide(
            request(header_from=["pat@example.net", "other@example.net"]),
            policy,
            rates(),
        )
        self.assertEqual(two_froms["reasons"], ["header_from_unauthenticated"])
        dmarc_fail = decide(request(dmarc_pass=False), policy, rates())
        self.assertEqual(dmarc_fail["reasons"], ["dmarc_not_passing"])
        custom_mail_from = decide(request(envelope_mail_from="bounce@example.net"), policy, rates())
        self.assertEqual(custom_mail_from["action"], SEND)

    def test_rule_cannot_widen_hello_audiences(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["allow_audiences"] = ["new_inquiry", "legal"]
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["reasons"], ["rule_audiences_too_wide"])

    def test_force_send_is_ignored(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["enabled"] = False
        forced = request(force_send=True, authorized=True, chat_approved=True)
        self.assertEqual(decide(forced, policy, rates())["reasons"], ["rule_disabled"])

    def test_freeform_policy_fails_closed(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["allow_freeform"] = True
        self.assertEqual(decide(request(), policy, rates())["reasons"], ["freeform_not_permitted"])

    def test_low_confidence_attachment_and_rate_limit(self):
        policy = enabled_hello_policy()
        self.assertEqual(decide(request(confidence=0.5), policy, rates())["reasons"], ["confidence_below_threshold"])
        self.assertEqual(decide(request(has_attachment=True), policy, rates())["reasons"], ["attachment_present"])
        self.assertEqual(
            decide(request(), policy, rates(role_sent_last_hour=20))["reasons"],
            ["rate_limited"],
        )

    def test_missing_rate_state_fails_closed(self):
        self.assertEqual(decide(request(), enabled_hello_policy(), None)["reasons"], ["rate_state_unavailable"])

    def test_kill_switch_blocks_approved_human_and_automatic_sends(self):
        default = json.loads(
            (ROOT / "shared" / "policies" / "auto-reply-authorization.example.json").read_text(encoding="utf-8")
        )
        message = human_message()
        approval = approval_for(message)
        stopped = decide(request(role="support"), default, rates())
        self.assertEqual(stopped["reasons"], ["kill_switch_global"])
        self.assertFalse(
            deliver(default, message, req=request(role="support"), approval=approval, allow_hosts=[], required_assets=[])
        )
        automatic = enabled_hello_policy()
        self.assertTrue(deliver(automatic, template_message()))
        enabled = enabled_hello_policy()
        enabled["kill_switch"]["global"] = True
        killed = decide(request(), enabled, rates())
        self.assertEqual(killed["action"], STOP)
        self.assertFalse(deliver(enabled, template_message(), approval=approval_for(template_message())))
        role_policy = enabled_hello_policy()
        role_policy["kill_switch"]["roles"] = {"hello": True}
        role_killed = decide(request(), role_policy, rates())
        self.assertEqual(role_killed["reasons"], ["kill_switch_role"])
        self.assertFalse(deliver(role_policy, template_message(), approval=approval_for(template_message())))

    def test_approval_is_bound_to_the_exact_message_and_is_single_use(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["human_only_roles"].append("hello")
        policy["auto_reply"]["rules"][0]["enabled"] = False
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["reasons"], ["role_requires_human"])
        message = template_message()
        approval = approval_for(message)
        ledger = ReservationLedger()
        self.assertTrue(deliver(policy, message, approval=approval, ledger=ledger))
        self.assertFalse(deliver(policy, message, approval=approval, ledger=ledger))
        other = template_message(html=message["html"] + "<p>Different offer.</p>")
        self.assertEqual(approval_problem(other, approval), "approval_mismatch")
        self.assertFalse(deliver(policy, other, approval=approval))
        swapped = template_message(to=["other@example.net"])
        self.assertFalse(deliver(policy, swapped, approval=approval))
        hidden = template_message(bcc=["hidden@example.org"])
        self.assertFalse(deliver(policy, hidden, approval=approval_for(template_message())))
        swapped_sender = template_message(**{"from": "sales@example.com"})
        self.assertFalse(deliver(policy, swapped_sender, approval=approval))
        short = approval_for(message, payload_sha256="sha256:exampledigest")
        self.assertEqual(approval_problem(message, short), "approval_digest_invalid")
        self.assertIsNone(approval_problem(message, approval))
        self.assertFalse(
            delivery_allowed(
                request=request(),
                policy=policy,
                rate_state=rates(),
                message=message,
                approval=approval,
                ledger=None,
                template_text=TEMPLATE_TEXT,
                template_html=TEMPLATE_HTML,
                template_subject=TEMPLATE_SUBJECT,
                template_version=TEMPLATE_VERSION,
                template_variables=VARIABLES,
                allow_hosts=["assets.example.com"],
                required_assets=[ASSET],
            )
        )
        chat = dict(approval)
        del chat["payload_sha256"]
        chat["chat_transcript"] = "approved"
        self.assertEqual(approval_problem(message, chat), "approval_digest_invalid")

    def test_null_reverse_path_is_not_overridden_by_approval(self):
        policy = enabled_hello_policy()
        message = human_message()
        self.assertFalse(
            deliver(
                policy,
                message,
                req=request(envelope_mail_from="<>"),
                approval=approval_for(message),
                allow_hosts=[],
                required_assets=[],
            )
        )


if __name__ == "__main__":
    unittest.main()
