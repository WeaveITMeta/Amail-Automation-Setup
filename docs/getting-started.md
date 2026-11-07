# Getting started

The checklist in the [README](../README.md) is the canonical list. These notes are the operator cautions next to it.

- Region: receiving endpoints are a subset of SES regions. Sandbox status is per region. Read `aws sesv2 get-account` before you promise anyone a reply.
- Names: use your domain. The strings `example.com` and `example-com-inbound-mail` are documentation. Buckets are globally unique.
- Secrets: use the worker role. If you must type a key, use silent `read` as the README shows, then unset it. Do not echo it to prove it was set.
- Wake: write the chosen alternative into the deployment notes. Disable the other subscriptions.
- State: create the key store first. Rehearse a disk wipe. The key is still there, or you are not done.
- Mail: the first external message is a simulator send approved by a person. Customers come after that.
- Policy: start from the human-only file. The Hello file is a shape to test, shipped disabled.
- Artwork: put a public HTTPS file on an allowlisted host and look at the rendered HTML, including the image request, before you call the draft send-ready.
- CI: `python3 -m unittest discover -s tests -v` on every policy or skill change. That command is a shell example. It does not install Amail and it does not send mail.
- Client: people read the mailbox in Amail on Windows, macOS, or Linux, or in NOVA, Grok Bot, or another compatible client. The worker that handles SES is a separate process.

Nothing in this repository applies those steps for you.
