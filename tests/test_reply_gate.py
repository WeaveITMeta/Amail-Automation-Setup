"""Authorization gate tests. No network and no mailbox."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.reply_gate import HUMAN, SEND, STOP, decide, delivery_allowed  # noqa: E402


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
        "has_attachment": False,
        "freeform_body": False,
        "is_follow_up": False,
        "thread_already_replied": False,
        "is_test_or_notice": False,
        "suppression_or_opt_out": False,
        "already_sent": False,
        "already_pending_send": False,
        "virus_verdict_fail": False,
        "spam_verdict_fail": False,
    }
    base.update(overrides)
    return base


def enabled_hello_policy():
    path = ROOT / "shared" / "policies" / "hello-first-reply.example.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy = copy.deepcopy(policy)
    policy["kill_switch"]["global"] = False
    policy["auto_reply"]["rules"][0]["enabled"] = True
    return policy


class GateTests(unittest.TestCase):
    def test_shipped_default_stops_on_kill_switch(self):
        policy = json.loads(
            (ROOT / "shared" / "policies" / "auto-reply-authorization.example.json").read_text(encoding="utf-8")
        )
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["action"], HUMAN)
        self.assertEqual(decision["reasons"], ["kill_switch_global"])

    def test_shipped_hello_file_does_not_send(self):
        policy = json.loads(
            (ROOT / "shared" / "policies" / "hello-first-reply.example.json").read_text(encoding="utf-8")
        )
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["action"], HUMAN)
        self.assertNotEqual(decision["action"], SEND)

    def test_rubric_pass_without_enabled_rule_does_not_send(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["enabled"] = False
        decision = decide(request(rubric_pass=True), policy, rates())
        self.assertEqual(decision["action"], HUMAN)
        self.assertEqual(decision["reasons"], ["rule_disabled"])

    def test_enabled_rule_without_rubric_does_not_send(self):
        decision = decide(request(rubric_pass=False), enabled_hello_policy(), rates())
        self.assertEqual(decision["reasons"], ["rubric_not_passed"])

    def test_explicit_narrow_grant_sends_template(self):
        decision = decide(request(audience="routing"), enabled_hello_policy(), rates())
        self.assertEqual(decision["action"], SEND)
        self.assertEqual(decision["template_id"], "hello-first-inquiry")
        self.assertEqual(decision["reasons"], ["explicit_rule_and_rubric"])

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
        ]
        for overrides, action, reason in cases:
            decision = decide(request(**overrides), policy, rates())
            self.assertEqual(decision["action"], action, overrides)
            self.assertEqual(decision["reasons"], [reason], overrides)

    def test_rule_cannot_widen_hello_audiences(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["allow_audiences"] = ["new_inquiry", "legal"]
        decision = decide(request(), policy, rates())
        self.assertEqual(decision["reasons"], ["rule_audiences_too_wide"])

    def test_force_send_is_ignored(self):
        policy = enabled_hello_policy()
        policy["auto_reply"]["rules"][0]["enabled"] = False
        forced = request(force_send=True, authorized=True)
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

    def test_delivery_respects_hard_stops_and_human_approval(self):
        approval = {
            "permission": "send",
            "decision": "approved",
            "approver": "person",
            "draft_id": "draft_example_001",
            "rendered_sha256": "sha256:exampledigest",
        }
        sent = decide(request(), enabled_hello_policy(), rates())
        self.assertTrue(delivery_allowed(decision=sent, approval=None, rendered_ok=True))
        self.assertFalse(delivery_allowed(decision=sent, approval=None, rendered_ok=False))
        held = decide(request(audience="legal"), enabled_hello_policy(), rates())
        self.assertFalse(delivery_allowed(decision=held, approval=None, rendered_ok=True))
        self.assertTrue(delivery_allowed(decision=held, approval=approval, rendered_ok=True))
        notice = decide(request(is_test_or_notice=True), enabled_hello_policy(), rates())
        self.assertFalse(delivery_allowed(decision=notice, approval=approval, rendered_ok=True))
        spam = decide(request(spam_verdict_fail=True), enabled_hello_policy(), rates())
        self.assertFalse(delivery_allowed(decision=spam, approval=None, rendered_ok=True))
        self.assertTrue(delivery_allowed(decision=spam, approval=approval, rendered_ok=True))
        agent_approval = dict(approval, approver="agent")
        self.assertFalse(delivery_allowed(decision=held, approval=agent_approval, rendered_ok=True))


if __name__ == "__main__":
    unittest.main()
