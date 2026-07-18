# Security policy

Do not disclose vulnerabilities, credentials, personal data, or private Nero
state in a public issue or pull request.

GitHub private vulnerability reporting is part of the desired repository
configuration but was disabled in the live baseline on 2026-07-18. Until Toni
explicitly enables it, contact Toni through an existing private channel with a
minimal description and no reusable secret. Once enabled, use the repository's
**Security > Report a vulnerability** flow.

Reports should include the affected revision, impact, reproduction steps,
whether exploitation changes local or remote state, and a safe remediation
proposal. Rotate any exposed credential immediately; removing it from the
latest commit is not sufficient because Git history and logs may retain it.
