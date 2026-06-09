# 🔐 Security Policy

Please do not report security issues publicly.

For now, open a private advisory or contact the maintainer directly.

## Sensitive data rules

Never commit:

- API keys
- `.env` files
- customer documents
- private reports
- generated ZIP archives
- logs containing request payloads or secrets

## AI provider keys

Provider keys should be supplied through environment variables, Docker secrets, or a future encrypted/BYOK workflow.
