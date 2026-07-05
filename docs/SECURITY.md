# ArtiChat Security Policy

ArtiChat is designed for self-hosted deployments where administrators control users, model connections, tools, functions, files, and network access. Security issues should be evaluated against that deployment model.

## Supported Versions

| Version (Branch) | Supported |
| ---------------- | --------- |
| main             | yes       |
| dev              | no        |
| others           | no        |

## Reporting

Report suspected vulnerabilities through the private security channel configured for this repository or deployment. Do not publish exploit details before a fix is available to affected operators.

Reports should include:

- Affected version or commit.
- Deployment configuration needed to reproduce the issue.
- Exact reproduction steps.
- Expected result and actual result.
- Impacted security boundary: confidentiality, integrity, availability, authenticity, or non-repudiation.
- Suggested remediation when available.

## Out Of Scope

These are normally not treated as vulnerabilities:

- Issues requiring an administrator to intentionally install malicious code, weaken security settings, or connect untrusted services.
- User actions that only affect the reporter's own data, account, browser session, or local environment.
- Expected behavior of administrator-only tools and functions that execute server-side code.
- Reports without actionable reproduction steps.

## Administrator Guidance

Only grant tool and function creation permissions to users you trust with server-level access. Review external model, tool, webhook, storage, and authentication integrations before enabling them in production.

## Disclosure

Coordinate disclosure privately until a fix is available. Public release notes should describe impact and remediation without exposing unnecessary exploit detail.
