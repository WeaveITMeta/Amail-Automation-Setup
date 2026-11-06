# Event schemas

The JSON Schemas under [shared/schemas/](../shared/schemas/handled-record.schema.json) describe the documents this template talks about. They are not the full AWS SES schemas. Examples under [examples/events/](../examples/events/inbound-event.json) are fictional and are checked by `scripts/validate_library.py`.

| Example | Schema | What it is |
| --- | --- | --- |
| [ses-receipt-notification.json](../examples/events/ses-receipt-notification.json) | [ses-receipt-notification.schema.json](../shared/schemas/ses-receipt-notification.schema.json) | Subset of an S3 receipt notification. No message body. |
| [inbound-event.json](../examples/events/inbound-event.json) | [inbound-event.schema.json](../shared/schemas/inbound-event.schema.json) | Internal wake. `access` is `read_only`. |
| [handled-record.json](../examples/events/handled-record.json) | [handled-record.schema.json](../shared/schemas/handled-record.schema.json) | Immutable key. |
| [attempt-record.json](../examples/events/attempt-record.json) | [attempt-record.schema.json](../shared/schemas/attempt-record.schema.json) | One append-only attempt. |
| [triage-report.json](../examples/events/triage-report.json) | [triage-report.schema.json](../shared/schemas/triage-report.schema.json) | Internal report. `external_send` is `not_authorized` in the example. |
| [draft-record.json](../examples/events/draft-record.json) | [draft-record.schema.json](../shared/schemas/draft-record.schema.json) | Permission `draft`, with threading and an HTTPS asset. |
| [approval-record.json](../examples/events/approval-record.json) | [approval-record.schema.json](../shared/schemas/approval-record.schema.json) | Permission `send`, approver `person`, `payload_sha256` of [approved-delivery.json](../examples/events/approved-delivery.json). |

`wake_source` is an enum: `sns_worker_queue`, `coordinator_fanout`, `peer_wake`, `direct_webhook`, or `other`. The example uses `coordinator_fanout` because that was one of the verified alternatives, not because it is mandatory. Change it to the path you actually run.

Bounce and complaint events come from the configuration set, not from the receipt notification. Handle permanent bounces and complaints by suppression. Do not store the complaint body in the application log.
