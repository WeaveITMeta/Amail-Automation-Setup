# Reference checks

These modules are imported by the tests. They do not open a network connection, read a mailbox, or call AWS.

| Module | Behavior |
| --- | --- |
| `reply_gate.py` | Authorization decision. Rubric pass is required and not sufficient. |
| `preflight.py` | Tests, notices, and no-reply senders, before a draft. |
| `idempotency.py` | Honors an atomic create-if-absent result. |
| `object_ref.py` | Bucket and key come from the wake and the configured bucket only. |
| `templates.py` | Only `organization` and `role_display` placeholders. |
| `send_ready.py` | HTTPS allowlist, no `cid:`, threading headers. |
| `schema_check.py` | The JSON Schema subset used by this repo. |

`delivery_allowed` refuses hard stops even when a person approval is present. `template_send` still requires the rendered checks. The caller must pass the decision returned by `decide`, using a policy file the agent cannot edit and flags the agent cannot set.
