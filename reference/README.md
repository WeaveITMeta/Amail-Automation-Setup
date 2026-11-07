# Reference checks

These modules are imported by the tests. They do not open a network connection, read a mailbox, or call AWS.

| Module | Behavior |
| --- | --- |
| `reply_gate.py` | Policy decision. Rubric pass is required and not sufficient. The kill switch stops every send. |
| `binding.py` | Digest of the exact outbound message, including From, To, Cc, Bcc, and Reply-To, plus template byte match. |
| `reservation.py` | In-process atomic claim. Not a durable store. `handoff_started` is not retried. |
| `preflight.py` | Tests, notices, and no-reply senders, before a draft. |
| `idempotency.py` | Honors an atomic create-if-absent result. |
| `object_ref.py` | Bucket and key come from the wake and the configured bucket only. |
| `sns_wake.py` | Topic, certificate URL, and signature-required checks for an inbound S3 relay. It does not fetch the certificate, and it does not consume bounces. |
| `feedback.py` | Authenticated bounce and complaint ingestion, with freshness, replay, and rate checks. |
| `suppression.py` | Append-only log outside this repo. Every lookup re-reads it. |
| `unsubscribe.py` | RFC 8058 POST unsubscribe for promotional mail. GET does not suppress. |
| `sender_policy.py` | Per-class From allowlist. A postal address is not a From identity. |
| `outbound.py` | Mail-class header rules. Support replies do not require one-click headers. |
| `dns_auth.py` | SPF and DMARC text problems. It does not publish DNS. |
| `retry.py` | At most three transient attempts, and none after the send claim. |
| `templates.py` | Only `organization` and `role_display` placeholders. |
| `send_ready.py` | HTTPS allowlist, no `cid:`, threading headers. |
| `schema_check.py` | The JSON Schema subset used by this repo. |

`decide` does not send. `delivery_allowed` recomputes the decision and refuses the kill switch even when a person approval is present. Template sends must match the trusted render and the authorized From, To, Cc, Bcc, and Reply-To. Human sends must match `payload_sha256` of that same envelope, which includes the mail class. A ledger claim is required. Passing `ledger=None` refuses the send. Passing `suppression_log=None` also refuses the send. These checks do not make a mailbox production-ready. The in-process reservation ledger does not remember claims after the process exits. The suppression log remembers only what was written to its file, and a file on the worker disk is not the operator store.
