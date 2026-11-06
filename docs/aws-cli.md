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

Attach the S3 action to a rule whose bucket policy matches that rule name, then activate the set:

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
