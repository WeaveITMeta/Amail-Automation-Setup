# AWS CLI templates

These commands are not a setup script. Confirm each subcommand against `aws <service> help` for the CLI version you have. Substitute placeholders only after you confirm the account and region. Do not commit the substituted files if they contain live names you do not want published. `EXAMPLE_ACCOUNT_ID`, `REGION`, and `example-com-inbound-mail` are placeholders. The bucket name must be globally unique; the example may already be taken.

Export a profile and region. Do not pass access keys on the command line. Silent entry is described in the README.

## Read-only

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws sesv2 get-account --region "$AWS_REGION" --profile "$AWS_PROFILE"
aws ses describe-active-receipt-rule-set --region "$AWS_REGION" --profile "$AWS_PROFILE"
aws sesv2 get-email-identity --email-identity example.com --region "$AWS_REGION" --profile "$AWS_PROFILE"
```

Account output contains an account id. Leave it out of tickets and out of git.

## Identity and DNS values

Creating an identity is a change. Review it before you run it.

```bash
aws sesv2 create-email-identity \
  --email-identity example.com \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Read the DKIM tokens back and publish the three CNAMEs your DNS host shows you. The token values belong in DNS, not in this repo.

Custom MAIL FROM, again a change, on a subdomain that will not receive user mail:

```bash
aws sesv2 put-email-identity-mail-from-attributes \
  --email-identity example.com \
  --mail-from-domain bounce.example.com \
  --behavior-on-mx-failure USE_DEFAULT_VALUE \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Then publish:

| Name | Type | Value |
| --- | --- | --- |
| `example.com` | MX | `10 inbound-smtp.REGION.amazonaws.com` |
| `bounce.example.com` | MX | `10 feedback-smtp.REGION.amazonses.com` |
| `bounce.example.com` | TXT | `v=spf1 include:amazonses.com ~all` |
| `_dmarc.example.com` | TXT | `v=DMARC1; p=none; rua=mailto:dmarc-reports@example.com` |

Receipt rule sets use the v1 CLI. A minimal skeleton to review, not to run blindly:

```bash
aws ses create-receipt-rule-set \
  --rule-set-name acme-inbound \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Create the topic and queues before the receipt rule, because the rule's topic ARN has to exist. The rule file is [examples/aws/create-receipt-rule.example.json](../examples/aws/create-receipt-rule.example.json). It stores the object and publishes a pointer. It does not set `KmsKeyArn`. That field is the receipt action's client-side message encryption, which would make `GetObject` return ciphertext. SSE-S3 on the bucket is separate and is the minimal reference.

Create the dead-letter queue before the main queue. The redrive ARN in [examples/aws/inbound-queue-attributes.example.json](../examples/aws/inbound-queue-attributes.example.json) is a placeholder. Substitute the DLQ ARN from the first command before you create the main queue. `maxReceiveCount` is 5. Visibility timeout is 120 seconds, which must be longer than one handling attempt.

```bash
aws sqs create-queue \
  --queue-name example-inbound-dlq \
  --attributes file://examples/aws/dlq-attributes.example.json \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

aws sqs create-queue \
  --queue-name example-inbound \
  --attributes file://examples/aws/inbound-queue-attributes.example.json \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Allow SES to publish to the topic, then allow that topic to send to the queue. The policy documents are [examples/aws/sns-topic-policy.example.json](../examples/aws/sns-topic-policy.example.json) and [examples/aws/sqs-queue-policy.example.json](../examples/aws/sqs-queue-policy.example.json). `file://` supplies the attribute string on current AWS CLI v2. Confirm with `help` before you rely on it.

```bash
aws sns create-topic \
  --name example-inbound \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

aws sns set-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --attribute-name SignatureVersion \
  --attribute-value 2 \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

aws sns set-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --attribute-name Policy \
  --attribute-value file://examples/aws/sns-topic-policy.example.json \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

aws sqs set-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attributes "{\"Policy\":$(jq -c . examples/aws/sqs-queue-policy.example.json)}" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

`jq` is only here to compact the policy into the attribute string. If you do not have it, paste the JSON yourself. Do not put a secret in that string.

Subscribe the queue with the SNS envelope intact (`RawMessageDelivery=false`) so a consumer can verify the SNS signature. The HTTPS alternative for a Worker is below, in the Cloudflare notes. Confirm the subscription. SES does not start delivering because this subscribe command exists. The receipt rule has to name the topic, and the rule set has to be active.

```bash
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol sqs \
  --notification-endpoint "$QUEUE_ARN" \
  --attributes RawMessageDelivery=false \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Create the receipt rule only after `$TOPIC_ARN` in the example file has been replaced, then activate the set. Activating replaces whatever rule set was active in that region.

```bash
aws ses create-receipt-rule \
  --cli-input-json file://examples/aws/create-receipt-rule.example.json \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```


```bash
aws ses set-active-receipt-rule-set \
  --rule-set-name acme-inbound \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Activating a set replaces the previous active set in that region. Know what you are replacing.

The worker read:

```bash
aws s3api get-object \
  --bucket "$INBOUND_BUCKET" \
  --key "$OBJECT_KEY" \
  --region "$AWS_REGION" \
  --profile "$READ_ONLY_PROFILE" \
  "$LOCAL_EML"
```

There is intentionally no `aws s3 ls` loop here.

## Sending checks

Do not send to a live customer from a test. The simulator addresses are documented by AWS:

```bash
aws sesv2 send-email \
  --from-email-address hello@example.com \
  --destination 'ToAddresses=success@simulator.amazonses.com' \
  --content 'Simple={Subject={Data=ACME simulator test,Charset=utf-8},Body={Text={Data=Simulator test from the ACME template,Charset=utf-8}}}' \
  --region "$AWS_REGION" \
  --profile "$SENDER_PROFILE"
```

Run that only with the sender profile, only after a person has approved the test, and only from a verified identity. Sandbox accounts can send to the simulator. They cannot send to arbitrary customers.

This page omits `put-account-details`. Production access is a review you start in the SES console when you are ready, not a command this template runs for you.
