# Security Policy

## Supported Scope

Security reports are welcome for all code in this repository.

Priority focus areas:

- Authentication and session handling
- API input validation and output handling
- Queue and worker processing paths
- Secret and token handling
- Dependency vulnerabilities

## Reporting a Vulnerability (Private)

Please do not open public issues for security vulnerabilities.

Preferred reporting method:

1. Use GitHub Security Advisories for this repository (Security tab, Report a vulnerability).
2. Include a clear reproduction path and impact summary.

If Security Advisories are unavailable, contact the maintainer privately through the repository owner profile and include the same details.

## What to Include in a Report

Please include:

- Vulnerability type and affected component
- Reproduction steps
- Proof of concept (minimal and safe)
- Potential impact
- Suggested fix (optional)
- Environment details (OS, Python version, deployment mode)

## Response Process and Timeline

Target service levels:

- Acknowledgement: within 72 hours
- Initial triage: within 7 calendar days
- Status update cadence: at least weekly until resolution

Resolution targets after confirmation:

- Critical severity: fix or mitigation within 7 days
- High severity: within 14 days
- Medium severity: within 30 days
- Low severity: next planned release

These timelines are targets, not guarantees, and may vary with report complexity.

## Disclosure Policy

- We follow coordinated disclosure.
- Please allow time for a fix before public disclosure.
- Once patched, maintainers may publish an advisory with credit (if desired).

## Security Best Practices for Contributors

- Never commit secrets, tokens, or credentials.
- Use `.env` files locally and keep them out of version control.
- Validate and sanitize untrusted input.
- Avoid logging sensitive values (tokens, secrets, personal data).
- Prefer least-privilege tokens and minimal permissions.
- Keep dependencies up to date and review dependency risk.
- Add tests for security-relevant changes.

## Out of Scope

The following are generally out of scope unless combined with clear impact:

- Theoretical issues without reproducible impact
- Vulnerabilities only in unsupported third-party infrastructure
- Social engineering attempts
