# Reference checks

These modules are imported by the tests. They do not open a network connection, read a mailbox, or call AWS.

| Module | Behavior |
| --- | --- |
| `reply_gate.py` | Policy decision. Rubric pass is required and not sufficient. The kill switch stops every send. |
| `binding.py` | Digest of the exact outbound message, replay of approval ids, and template byte match. |
| `preflight.py` | Tests, notices, and no-reply senders, before a draft. |
| `idempotency.py` | Honors an atomic create-if-absent result. |
| `object_ref.py` | Bucket and key come from the wake and the configured bucket only. |
| `sns_wake.py` | Topic, certificate URL, and signature-required checks for an SNS wake. It does not fetch the certificate. |
| `templates.py` | Only `organization` and `role_display` placeholders. |
| `send_ready.py` | HTTPS allowlist, no `cid:`, threading headers. |
| `schema_check.py` | The JSON Schema subset used by this repo. |

`decide` does not send. `delivery_allowed` refuses the kill switch and other hard stops even when a person approval is present. Template sends must match the trusted render. Human sends must match `payload_sha256` and must use an approval id that has not been consumed. Chat text is not an approval. These checks passing does not mean a mailbox is in production.
