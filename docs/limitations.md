# Limitations

- Templates and a reference gate. No deployed inbox.
- Interview lessons are labeled. Wake path and the Hello grant are not universal.
- The gate trusts worker-supplied flags. The model must not set them.
- Hard content checks miss many kinds of sensitive data.
- Region limits, sandbox limits, and one active receipt rule set are AWS constraints. Confirm them in current AWS docs when you build.
- Email Routing and SES receiving do not share an MX hostname.
- A claimed key can sit unfinished until an operator appends a resume. That is the trade for not double-sending.
- This is not legal advice and not a compliance certification. Tests of the reference gate are not evidence that a live account suppresses, signs, or rate-limits.
- A public DNS observation can be recorded without this repository publishing a replacement record. Outbound sender inventory is a separate check. Do not add an SES include because a placeholder SPF record looks unfinished.
