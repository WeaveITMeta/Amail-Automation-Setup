# Deliverability, opt-out, and privacy

This note is guidance for the reference checks. It is not a legal opinion, not a compliance certification, and not evidence that a live account implements the checks. Sources were read on 7 November 2026.

## Three kinds of mail

| Class | What it is | One-click headers in this library |
| --- | --- | --- |
| Promotional bulk | Marketing or subscribed list mail | Required. Both headers. DKIM must cover both names. |
| Transactional | A receipt, reset, or similar notice about a request the recipient made | Not required |
| Customer support and other one-to-one replies | A reply to a person, including a support answer | Not required. Adding them is rejected so a support reply is not labeled as a list |

[Gmail's sender guidelines](https://support.google.com/mail/answer/81126), read 7 November 2026, require one-click unsubscribe for marketing and subscribed messages from bulk senders. The [Gmail FAQ](https://support.google.com/mail/answer/14229414) says one-click unsubscribe is not required for every message. It names transactional mail, such as password resets and reservation confirmations, as excluded. [Yahoo's FAQ](https://senders.yahooinc.com/faqs/), describing the February 2024 requirements, says the same: promotional and marketing messages, not transactional messages such as order confirmations and password resets. Yahoo does not decide the label for the sender. A support reply in this library is correspondence. It is not treated as promotional bulk. If the primary purpose of a particular support message is an advertisement, the CAN-SPAM primary-purpose test can still make that message commercial. This library does not make that call for a live message.

## One-click unsubscribe

[RFC 8058](https://www.rfc-editor.org/rfc/rfc8058) (January 2017) is the specification this reference follows for promotional mail:

- `List-Unsubscribe` contains one HTTPS URI. It may also contain a `mailto:` URI. [RFC 2369](https://www.rfc-editor.org/rfc/rfc2369) (July 1998) is the older list-header syntax and is not by itself the one-click signal.
- `List-Unsubscribe-Post` is the single pair `List-Unsubscribe=One-Click`.
- The receiver performs an HTTPS POST. The body is that same pair, as `application/x-www-form-urlencoded` or `multipart/form-data`.
- The POST must not depend on cookies or HTTP authorization. This reference rejects those requests and does not suppress.
- The sender must not answer the POST with an HTTPS redirect.
- A DKIM signature ([RFC 6376](https://www.rfc-editor.org/rfc/rfc6376), September 2011) must cover both header field names. This code checks that the caller supplied those names. It does not produce a signature. Missing names fail closed for promotional mail.
- GET and HEAD do not change suppression state, including when the token is valid. One-click is the POST. A GET can be a landing page. It is not a second confirmation the POST has to wait for, and it is not a login.

The reference POST is idempotent. A second valid POST stays suppressed and does not append another row.

Gmail's FAQ asks senders to honor unsubscribe requests within two days. Yahoo's best practices use the same two-day figure. The CAN-SPAM opt-out clock for commercial mail is different: the FTC guide says a request must be honored within 10 business days, and the mechanism must keep working for at least 30 days after the message was sent. Meeting a provider's two-day preference is not a statement that every statute uses that number.

## Commercial mail still needs a postal address

The FTC's [CAN-SPAM compliance guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business) tells commercial emailers to include a valid physical postal address, to identify the message as an ad, to use non-deceptive headers and subjects, and to offer an opt-out. [16 CFR Part 316](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-316) is the FTC rule, including the primary-purpose test and the definition of a valid physical postal address. 15 U.S.C. § 7704(a)(5) is the statutory requirement for the identifier and the postal address on commercial mail.

Prior consent does not delete that postal-address requirement for a message whose primary purpose is commercial. Transactional or relationship messages are largely outside the commercial rules when they are only that content, but they still cannot use false header information. This library does not embed a person's street address. Promotional bulk mail fails the reference check until the operator passes their own postal address at send time. That string is not accepted as the From address.

## Privacy and lawful basis

[Regulation (EU) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng) Article 6 lists lawful bases. Article 21(2) and 21(3) give a person the right to object to direct marketing, and say the data must no longer be processed for that purpose. [Directive 2002/58/EC](https://eur-lex.europa.eu/eli/dir/2002/58/oj/eng) Article 13 generally requires prior consent for email direct marketing, with a narrow similar-products exception that still needs an opt-out when the address is collected and on each message.

This repository does not store a lawful basis or a consent record. A passing test is not GDPR or ePrivacy compliance. An objection or an unsubscribe still has to be on the suppression log before another promotional send, including a retry.

## Loops, lists, and no-reply

[RFC 3834](https://www.rfc-editor.org/rfc/rfc3834) (August 2004) says an automatic response should not go out when `Auto-Submitted` is present with any value other than `no`, and the automatic response should carry `Auto-Submitted: auto-replied`. A null reverse path is not a reply destination. [RFC 5321](https://www.rfc-editor.org/rfc/rfc5321) uses `<>` for that path. The reference also stops drafts for `Precedence` values `bulk`, `junk`, `list`, and `auto-reply`, for `List-Id` and `List-Unsubscribe` on inbound mail, for `X-Auto-Response-Suppress` values `All` and `AutoReply`, and for no-reply and mailer-daemon local parts. Mail from one of the domain's own role addresses is treated as a loop.

Those stops apply before a draft. They are not a claim that a person is forbidden to write a new message outside this intake path.

## SPF, DKIM, and DMARC

[RFC 7208](https://www.rfc-editor.org/rfc/rfc7208) (April 2014) makes more than one SPF record at a name a permanent error. An `ip4` mechanism needs an IPv4 address. The literal token `YOUR_SERVER_IP` is not an address, so a record that contains it does not parse, and a trailing `~all` is not reached. [RFC 7489](https://www.rfc-editor.org/rfc/rfc7489) (March 2015) section 6.6.3 makes multiple DMARC records at the same name a permanent error. Two records that both say `p=none` are still a permanent error. An `rua` on only one of them does not pick a winner.

DKIM alignment is the reliable path for a custom bounce domain: the `d=` domain matches the header From domain. Relaxed SPF alignment is what lets a bounce subdomain align. Do not set `aspf=s` unless that alignment is intended. DMARC authenticates the header From. It does not choose the reply address. The reply target remains the authenticated header From.

[Amazon SES SPF for a custom MAIL FROM](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-spf.html) documents an MX at `feedback-smtp.<region>.amazonses.com` and an SPF TXT that includes `amazonses.com`. Publishing that include authorizes SES for that MAIL FROM name. This library's `ses_spf_change` refuses to rewrite a record. An unverified outbound inventory is not permission to add the include, and a verified inventory still does not make this code publish DNS.

[Yahoo's bulk-sender requirements](https://senders.yahooinc.com/best-practices/) (enforcement described as beginning February 2024) ask for SPF and DKIM, a DMARC policy of at least `p=none`, alignment of the header From, and a spam-complaint rate under 0.3 percent. Gmail's bulk-sender section uses the same 0.3 percent Postmaster Tools figure. Those are provider thresholds, not a certification that mail under the line will be delivered.

## Bounces, complaints, and suppression

[SES account-level suppression](https://docs.aws.amazon.com/ses/latest/dg/sending-email-suppression-list.html) can add hard bounces and complaints when those reasons are enabled. The same page says only hard bounces are added, and that a Gmail spam-button report is not fully reported to SES. A provider suppression list is not a complete opt-out log. Keep the local log.

The reference feedback consumer is separate from the inbound S3 relay:

- The relay checks an SNS signature flag supplied by an adapter, the topic ARN, and the certificate URL shape. It does not fetch the certificate. [SNS signature verification](https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html) stays with that adapter.
- Freshness, replay, and rate on the relay are unproven until the caller passes a clock, a seen-id set, and a rate result. `assess_inbound_relay` reports those gaps. It never suppresses.
- The feedback consumer verifies an authenticator over the string-to-sign, rejects a stale or future timestamp, rejects a replay of the same feedback id without applying the new recipient list, and refuses the event when the rate counter is missing or exhausted. Permanent bounces and complaints suppress. Transient bounces are recorded and do not suppress. `not-spam` does not suppress.

A skill sentence, a draft, and a unit test are not that consumer. If a deployment only has the instruction in an agent prompt, the control is not deployed.

## Rate, retry, and the human gate

The shipped policies cap automatic sends at 20 per role per hour, 3 per inbound sender per day, 2 per recipient per hour, and 3 per recipient per day. Transient provider errors may be considered at most 3 times, and only before the reservation claim. After `handoff_started`, the reference does not retry that key. A later human retry uses a new approval id and reads the suppression log again.

The configurable quality gate is the kill switch, the human-only role list, the confidence threshold, the rubric, and an enabled template rule. The default is human approval with the kill switch on. A rubric pass does not send.

## What the reference does not do

It does not send mail, publish DNS, assume an IAM role, or fetch an SNS certificate. It does not decide that a live mailbox is lawful. It does not treat the in-memory reservation ledger or a file on the worker disk as a multi-host store.
