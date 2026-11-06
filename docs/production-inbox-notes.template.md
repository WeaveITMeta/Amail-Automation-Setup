# Production inbox notes

Copy this file when a later interview is verified. Leave unknown fields as `unknown`. Do not paste mail, credentials, account ids, or live hostnames.

- Role label (generic, such as billing):
- Date verified:
- Active wake (one of: sns_worker_queue, coordinator_fanout, peer_wake, other, unknown):
- Paths that exist but are dormant:
- Raw MIME store (class only, such as s3-object):
- Reader identity (class only, such as read-only get-object on the woken key):
- Worker (managed Linux or other):
- Polling in use (yes only if an owner explicitly approved it):
- Handled key store (external and append-only, or other):
- Attempt log present (yes or no):
- Dead-letter path present (yes or no):
- Skill catalog path loaded before handling (yes or no):
- External send authority (human approval, or the exact intent of an owner grant):
- Artwork (public HTTPS host class, not a secret URL if the URL is private):
- Optional R2 (yes, no, or not used by this role):
- Optional Access-protected CRM (yes, no, or not used by this role):
- Difference from the reference:
- Evidence (interview id or ticket id, not a message body):
