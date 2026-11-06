# Lessons from a multi-role deployment

This page expands the README section with the same facts. It is not a runbook for a named company, and it does not include mail.

## Baseline you can reuse

Interviews agreed on the following, so the template treats them as the design:

- Raw MIME lives in S3. The wake carries the bucket and key.
- The worker is managed Linux. It uses the AWS CLI with an identity that can get the object and cannot send.
- Nobody polls the bucket, and nobody waits for an owner PC.
- The handled key is append-only and is created before the message is parsed.
- The role skill comes from the catalog before handling.
- Triage reports are automatic and internal.
- The sender is a different least-privilege identity.
- Per-role artwork is public HTTPS and is checked on the rendered HTML before send-ready review.

## Where that deployment was not uniform

Wake implementation differed. Document the live path per role. A direct webhook that does not fire is dormant. Do not "repair" it by leaving it subscribed next to a peer wake. Two active wakes are safe only because the handled key stops the second run, and they still confuse operators.

Authorization differed. Sales, support, and projects required a person for every external send and had no auto-reply permission. Hello had an owner-granted first reply limited to a genuine new lead, inquiry, or routing message, with follow-ups and partner, press, vendor, personal, legal, financial, government, spam, and no-reply excluded. That split is why policy is per role and per intent, and why the tests name those exclusions. The library default does not enable the Hello grant. The interviews did not include the reply text, so the template in `shared/templates/` is fictional ACME copy.

## What a bare key does not give you

Recommend, even if a given role only stored the key:

- An append-only attempt row for every wake, including duplicates and crashes.
- A dead-letter queue for the wake, reviewed by a person.
- Structured logs that keep the idempotency key, role, wake source, and outcome, and omit the MIME body.
- Thread-level "external reply already sent" memory before any first-reply rule is enabled. The message key will not stop a second message in the same conversation.

State has to remain after the workspace is replaced. A file in the checkout is not the handled store.

## Optional, not required

Some artwork was hosted on R2. Some CRM calls were protected by Cloudflare Access. Copy those only for roles that need them. Mail receipt does not.

## What not to copy

Do not copy tool bugs, internal product names, live hostnames, or message contents into this repository. If a later interview contradicts a line above, record the contradiction on [the blank notes template](production-inbox-notes.template.md) and change the reference in a reviewed pull request. Do not silently treat one role's wake as the diagram for all roles.
