# Architecture boundary

The reference architecture is SES receipt into an S3 object, one active wake that carries the object reference, a managed worker with a read-only identity, an append-only handled key, a catalog skill, an internal triage report, and a separate sender identity. One interviewed deployment ran that worker on Linux. Linux was the observed compute, not a rule that Amail itself runs only on Linux, and not a rule that only one agent client may open the mailbox. The separate sender is the recommended design. Interviews did not establish it for every role. Human approval is the default external-send mode, and the kill switch stops approved sends as well as automatic ones.

The mermaid diagram in the [README](../README.md) draws every wake alternative on purpose. A deployment selects one. Coordinator fan-out, an SNS-to-queue or Worker hop, and a peer wake with a dormant direct webhook are verified alternatives from one multi-role deployment. They are not three required stages.

Cloudflare DNS is an optional place to publish the SES records. A Cloudflare Worker on the SNS path is an optional wake adapter. Email Routing is an optional different ingress and uses different MX records. R2 and Access are optional and were not present for every role.

This repository does not ship the worker, the queue, or the receipt rule.
