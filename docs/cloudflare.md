# Cloudflare and SES

## DNS for the reference path

Cloudflare can host the zone. SES receives the mail. Create the records as DNS only:

| Record | Name | Value |
| --- | --- | --- |
| MX | `example.com` or the test subdomain | `10 inbound-smtp.REGION.amazonaws.com` |
| CNAME | the three Easy DKIM names SES returns | the matching `*.dkim.amazonses.com` targets |
| MX | `bounce.example.com` | `10 feedback-smtp.REGION.amazonses.com` |
| TXT | `bounce.example.com` | `v=spf1 include:amazonses.com ~all` |
| TXT | `_dmarc.example.com` | `v=DMARC1; p=none; rua=mailto:dmarc-reports@example.com` |

One SPF TXT per name. The apex does not need `include:amazonses.com` unless the apex itself is the MAIL FROM, which the reference avoids.

Proxy status does not apply to MX the way it applies to HTTP. Do not put Cloudflare's HTTP proxy in front of SES SMTP.

## What Cloudflare does not do in this design

- It does not accept the SMTP session that SES is supposed to receive.
- It does not implement receipt rules, spam verdicts, or the S3 action.
- It does not create SES DKIM keys.
- It does not move an account out of the SES sandbox.
- It does not apply the reply rubric or the kill switch.
- It does not send the customer reply. Outbound remains the SES sender identity in the reference.

## Email Routing as an alternate ingress

Email Routing is a separate product. Turn it on only for a hostname whose MX should be Cloudflare's, not SES. The dashboard publishes the current MX set and an SPF include. Copy those values from the current UI. The include has been documented as `include:_spf.mx.cloudflare.net`. Hostnames under `mx.cloudflare.net` have changed before, so a copied hostname from an old blog is not a source of truth.

While those MX records are present, do not also publish `inbound-smtp` on that name. Cloudflare documents that Email Routing stays off until competing MX records are removed.

Routing does not store the mailbox for your agent. A Worker on that path must write the raw MIME somewhere durable and then wake the role agent with an object reference. Routing does not give you an SMTP server for the outbound reply. Keep SES, or another sender you operate, for that send, with the same human-approval default.

Do not forward Email Routing into SES and also subscribe SES receipt on the same address. You will not get a clean single copy, and SPF will describe the forwarder rather than the original sender.

## Optional R2 and Access

Artwork URLs can be HTTPS on a hostname that happens to be backed by R2. The skill checks the URL, not the vendor. Access can sit in front of a CRM API a role reads for context. A role with no CRM client does not configure Access. Neither product is on the mail path.
