# Deployment evidence checklist

Reference tests are not deployment evidence. This page records what an operator still has to prove, plus one public DNS observation from 7 November 2026. It does not change DNS, IAM, or a receipt rule. No message was sent while it was written.

The sender role name below is an audit label for one support identity. It is not a universal From address, and it is not permission to send.

## Public DNS, queried 2026-11-07 02:36:08 UTC

Resolver answer was NOERROR. TTL was 300. The name servers in the same lookup were `koa.ns.cloudflare.com` and `zita.ns.cloudflare.com`.

SPF, one TXT at `amail.world`:

```text
v=spf1 ip4:YOUR_SERVER_IP ~all
```

DMARC, two TXT records at `_dmarc.amail.world`:

```text
v=DMARC1; p=none; rua=mailto:postmaster@Amail.World
v=DMARC1; p=none;
```

Problems, under [RFC 7208](https://www.rfc-editor.org/rfc/rfc7208) and [RFC 7489](https://www.rfc-editor.org/rfc/rfc7489):

- `ip4:YOUR_SERVER_IP` is not an IPv4 address. The SPF record does not parse. `~all` is not reached. This is a permanent error, not a soft fail.
- Two DMARC TXT records at one name are a permanent error. Both say `p=none`. That does not make the set valid. The `rua` on only one record does not choose a winner.
- Outbound sending inventory was not verified. Do not add `include:amazonses.com`, and do not replace these records from this repository. `reference/dns_auth.py` refuses that rewrite even when a caller says the inventory is verified.

## Support sender, not verified end to end

Audit labels, not a policy document this repository could read:

- The support sender profile is `weave-support-inbox-send`.
- It is not `weave-help-inbox-send`. A similar name is a different role.
- STS for that profile succeeded.
- The IAM policy read was denied, so `ses:SendEmail` and `ses:SendRawEmail` were not shown to be limited to `help@weave.support`.
- That restriction stays unverified. Do not edit the role from this repository. The example in `examples/iam/sender-role.example.json` is an `example.com` sketch.

## Inbound path the audit could see

- The SES receipt rule was enabled and scanning was on.
- An S3 range read of a stored object worked.
- This repository did not repeat those calls. Do not treat this file as a fresh AWS read.

## Suppression and the sending wrapper

- Operational suppression was documented as agent instructions.
- An active sending wrapper was not found.
- `reference/suppression.py` is the contract for a log that is read again before every send, including a retry. A green unit test does not mean that log is in the request path.

## Inbound relay is not the feedback consumer

- A local SNS inbound relay validated a signature.
- Topic binding was conditional on the configured topic.
- Freshness, replay, rate limits, and bounce handling were not demonstrated on that relay. They might exist in a downstream program. This audit did not see them there.
- Bounces and complaints belong to the configuration-set consumer in `reference/feedback.py`. The relay must not be described as that consumer.

## Marketing headers versus support mail

- Promotional bulk mail needs both RFC 8058 headers, DKIM coverage of both names, an HTTPS POST that suppresses, and a GET that does not. The POST must not require a login or a second confirmation.
- A valid physical postal address is still required for commercial mail when the recipient previously consented. Do not hardcode a personal street address as the sender identity.
- A genuine support reply is not that promotional message. One-click headers are not required on it.
- Nothing here certifies CAN-SPAM, GDPR, or ePrivacy compliance. The citations are in [deliverability-and-privacy.md](deliverability-and-privacy.md).

## Residual checks a person still has to do

- Publish one SPF record whose mechanisms match the real outbound senders, after that inventory exists.
- Publish one DMARC record, and confirm a second TXT is gone.
- Confirm the provider signs `List-Unsubscribe` and `List-Unsubscribe-Post` on a real promotional message.
- Read the support sender policy with an identity that is allowed to read it, and confirm the From condition.
- Run a full reply test only when sending is explicitly in scope. It was not in scope for this change.
- Alarm on complaint rate and bounce rate in the account that actually sends. Gmail's spam button is not a complete SES complaint feed.
