# Approval and automatic send

Default file: [auto-reply-authorization.example.json](../shared/policies/auto-reply-authorization.example.json).

Every role is human-only. The kill switch is on. There are no rules. Internal triage still runs.

Example file, not a recommendation: [hello-first-reply.example.json](../shared/policies/hello-first-reply.example.json).

It records one observed grant:

- Role `hello`
- Intent `first_reply_new_inquiry`
- Audiences `new_inquiry` and `routing`
- Template `hello-first-inquiry`
- Follow-ups denied
- Excluded audiences denied even if a future edit adds them to the allowlist, because the reference gate rejects a wider allowlist
- `enabled` is false and the global kill switch is true

Sales, support, and projects remain in `human_only_roles` in that file, matching the interview: those roles had no auto-reply permission.

A person approves one rendered draft. The review tool stores `payload_sha256` for that draft's From, recipients, subject, text, HTML, template id, and template version, plus a single-use `approval_id`. The sender recomputes the digest. A chat transcript is not an input to that check.

The automatic path does not read an approval the model wrote. `delivery_allowed` calls `decide` again and compares the message From, To, Cc, Bcc, and Reply-To with the envelope that decision authorized. The subject, text, and HTML must equal the trusted template. A template id by itself is not enough, and editing the decision object is not an input.

Both paths then claim the send key on a `ReservationLedger`. The reference class is in-process and atomic. It is not durable storage. The claim moves the key to `handoff_started` before the provider call. A crash after that claim, a timeout, or any unknown result must not trigger another automatic send of the same key. Record `ambiguous` and stop. A human retry uses a new approval id. Do not treat a new empty ledger after a restart as proof that the previous handoff did not happen.

The kill switch is an unconditional stop. A stored approval does not override it. The same is true for duplicates, virus failures, tests, notices, suppression, opt-out, no-reply senders, and a null reverse path.

DMARC authenticates the header From. The automatic destination is that address. The envelope MAIL FROM is not a reply target, including when it is `<>`.

The fictional Hello body says a person will review the inquiry and states no price or partnership. If an owner's real first reply says something else, they replace the template in their own policy change and review the new HTML. They do not paste a live message into this repo.
