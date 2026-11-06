"""Reservation ledger tests. The ledger is in-process, not a durable service."""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.reservation import ReservationLedger  # noqa: E402

DIGEST = "sha256:" + ("ab" * 32)


class ReservationTests(unittest.TestCase):
    def test_one_claim_then_every_later_claim_fails(self):
        ledger = ReservationLedger()
        self.assertTrue(ledger.claim_handoff("approval_example_001", DIGEST))
        self.assertEqual(ledger.state("approval_example_001"), "handoff_started")
        self.assertFalse(ledger.claim_handoff("approval_example_001", DIGEST))
        self.assertTrue(ledger.mark_ambiguous("approval_example_001"))
        self.assertFalse(ledger.claim_handoff("approval_example_001", DIGEST))
        self.assertFalse(ledger.mark_sent("approval_example_001", "provider-id"))

    def test_sent_key_is_not_retried(self):
        ledger = ReservationLedger()
        self.assertTrue(ledger.claim_handoff("auto:EXAMPLE_SES_MESSAGE_ID", DIGEST))
        self.assertTrue(ledger.mark_sent("auto:EXAMPLE_SES_MESSAGE_ID", "ses-example-id"))
        self.assertEqual(ledger.state("auto:EXAMPLE_SES_MESSAGE_ID"), "sent")
        self.assertFalse(ledger.claim_handoff("auto:EXAMPLE_SES_MESSAGE_ID", DIGEST))
        self.assertFalse(ledger.mark_sent("auto:EXAMPLE_SES_MESSAGE_ID", "ses-example-id"))

    def test_concurrent_claims_have_one_winner(self):
        ledger = ReservationLedger()
        barrier = threading.Barrier(8)
        results = []
        lock = threading.Lock()

        def attempt():
            barrier.wait()
            won = ledger.claim_handoff("approval_example_001", DIGEST)
            with lock:
                results.append(won)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(True), 1)
        self.assertEqual(ledger.state("approval_example_001"), "handoff_started")

    def test_a_new_ledger_does_not_remember_another_process(self):
        first = ReservationLedger()
        self.assertTrue(first.claim_handoff("approval_example_001", DIGEST))
        second = ReservationLedger()
        self.assertIsNone(second.state("approval_example_001"))
        self.assertTrue(second.claim_handoff("approval_example_001", DIGEST))
