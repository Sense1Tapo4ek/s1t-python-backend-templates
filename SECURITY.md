# Security Policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting:
[Security -> Report a vulnerability](https://github.com/Sense1Tapo4ek/s1t-python-backend-templates/security/advisories/new).

Do not open public issues for security findings. Expect an acknowledgement
within a week.

## Scope

This is a template. The auth stack (JWT, API keys, admin token, argon2id
hashing, CSRF, rate limiting) is in scope. Deployment hardening of forks is
the fork owner's responsibility -- see the PROD checklist in `.env.example`
and the deliberately-open example endpoints noted in
[docs/architecture.md](docs/architecture.md).

## Supported versions

Only the latest `main` is supported; the template has no release branches.
