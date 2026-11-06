# Operations

## Observability

Count received, claimed, duplicate, suppressed, test or notice, triaged, drafted, pending approval, person-sent, template-sent, send-failed, bounce, complaint, and dead-letter depth. Alarm on dead letters, complaint rate, bounce rate, and any template send while the kill switch is on.

Log lines look like the redacted example in the README. They are structured so a workspace reset does not take the only copy of the outcome. The attempt row is that copy.

## Retries and dead letters

Receipt failures are SES retries. If the bucket policy is wrong, fix the policy. A public bucket is not a retry strategy.

Queue deliveries are at-least-once. The conditional handled-key create makes the second delivery a duplicate attempt. Set the visibility timeout longer than a sober upper bound on one attempt so a slow worker is not retried while it is still running.

After several receives, the wake message sits on a dead-letter queue. An operator reads the error class, not the body, and decides whether to append a resume attempt. Redrive does not send email by itself.

Classify permanent failures (bad wake, missing skill, virus quarantine, suppression) so they record an outcome instead of cycling until the dead-letter queue fills with the same message.

## Testing

Repo tests do not need AWS:

```bash
python3 -m unittest discover -s tests -v
```

Live tests use a subdomain and the SES simulator. The notice fixture and any suppressed address produce no draft. The inquiry fixture produces one draft and, on redelivery, none. A person sends the simulator message with the sender role.

Hello exclusion tests belong in CI through `tests/test_reply_gate.py`. Re-run them when the policy files change.

## Rollout

Follow the README checklist. The extra operational rule is: one live wake per role. Record the dormant ones. Cut over a test subdomain before the apex. Keep the kill switch on through the MX change. Rollback is the kill switch, then the previous MX or a disabled rule. Do not delete keys as part of rollback.

## Troubleshooting

Use the table in the README. When a webhook looks configured and nothing runs, assume it might be the dormant path from the interviews and look for the peer or coordinator that holds the live subscription.

## Cost

No prices are listed. Drivers are in the README: SES receive and send, S3, KMS, SNS, SQS, compute, the state store, logs, cross-region transfer, optional dedicated IPs, optional NAT, optional Worker or R2 or Access, and the drafting model. Confirm numbers in the provider calculators for your region.
