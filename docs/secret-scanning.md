# Secret scanning

`scripts/validate_library.py` fails the tree when it finds:

- `AKIA` or `ASIA` access-key prefixes
- PEM private keys
- Slack webhook hosts
- live Stripe secret keys shaped like `sk_live_`
- GitHub token prefixes
- a 12-digit AWS account id inside an ARN
- a short denylist of organization tokens that do not belong in this template (the denylist lives in the script so the words are not repeated here)
- email addresses whose domain is not `example.com`, `example.net`, `example.org`, `amazonses.com`, or `amazonaws.com`

Addresses on the SES mailbox simulator are allowed because they are AWS test endpoints.

The scan does not print the matching secret. It prints the file and the rule name. If the match is real, rotate the credential, remove it from git history with the host's documented purge process, and do not paste it into chat to confirm.

The scan misses secrets that do not match these shapes. Run a second scanner locally if you handle live keys. CI uses the standard library only.

Do not store `.env`, `.aws/`, or `*.pem` in the tree. `.gitignore` covers those names. A gitignore rule is not a substitute for rotating a key that was committed once.
