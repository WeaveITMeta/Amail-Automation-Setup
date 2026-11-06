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

A person approves a rendered draft by writing an approval record with `approver` equal to `person` and `permission` equal to `send`. The sender checks that record for the human path. The automatic path never reads an approval the model wrote. It calls `decide` with the operator policy.

Hard stops ignore a person approval: duplicates, virus failures, tests, notices, suppression, opt-out, and no-reply senders. Those do not get a reply from this sender.

The fictional Hello body says a person will review the inquiry and states no price or partnership. If an owner's real first reply says something else, they replace the template in their own policy change and review the new HTML. They do not paste a live message into this repo.
