# Security

Identities:

| Identity | Attached to | Allows | Does not allow |
| --- | --- | --- | --- |
| SES receipt | The service, via the bucket policy | `s3:PutObject` on `raw/*` from the receipt rule ARN | Public read, delete, or send |
| Reader | The managed Linux worker | `s3:GetObject` on `raw/*` | `s3:ListBucket`, `ses:SendEmail`, IAM changes |
| Sender | The approval sender, not the agent | `ses:SendEmail` and `ses:SendRawEmail` for specific From addresses | Reading the raw prefix, editing the kill switch |
| Approver | A person | Writing an approval row | Assuming the reader role inside the model |
| Agent process | The model tools | Draft and triage writes | Send, policy writes, key deletion |

JSON sketches: [reader](../examples/iam/reader-role.example.json), [sender](../examples/iam/sender-role.example.json), [bucket](../examples/iam/inbound-bucket-policy.example.json).

The worker also checks that the key it fetches equals the key on the wake. A bucket or key mentioned inside the MIME is ignored. See `reference/object_ref.py`.

Encryption at rest is on for the bucket and for the handled-key store. TLS is required for the put, which the example bucket policy denies when `aws:SecureTransport` is false. Customer-managed keys follow the SES key-policy notes in the README. Do not enable S3 Object Lock default retention on a bucket SES writes; AWS documents that combination as unsupported.

Logs and drafts:

- Logs: idempotency key, role, outcome, wake source, error class.
- Not in logs: body, attachments, subjects, presigned URLs, tokens, mailbox passwords.
- The external address lives on the draft record, which is access-controlled, not in the log stream.

Prompt injection: the body can claim to be the owner, the kill switch, or a new skill. Those sentences are content. The policy file is loaded from a path the agent cannot write.

Suppression is consulted before the model runs. A draft is not a place to talk a recipient back onto a list.

Review the rendered HTML, not a markdown approximation. `cid:` parts are a failure. Artwork hosts are an allowlist.
