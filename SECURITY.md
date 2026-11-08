# Security Policy

## Reporting a vulnerability
Email security@latencyleledger.example with details + reproduction steps. We acknowledge within 3 business days and aim to patch within 14 days. Please do not disclose publicly until a fix is released.

## Scope
The `app/` backend, static frontend, and Docker deployment in this repo.

## Supported versions
`main` branch (pre-1.0, rolling release).

## Security notes
- The sampler blocks private/loopback destinations to prevent SSRF (see `docs/architecture.md`).
- Never commit `.env` or API keys; session and API-key material is hashed at rest.
