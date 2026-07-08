# 🧙‍♂️⛏️ MarkForge

**Forging Markdown from stubborn documents.**

MarkForge is a self-hosted document conversion forge that turns **DOCX, DOC, ODT and PDF** files into clean Markdown packages, with figures, optional AI cleanup, token visibility, and quality reporting.

It is built for technical documentation, Obsidian vaults, MkDocs sites, RAG pipelines, engineering knowledge bases, and anyone who has ever looked at a Word document and whispered: _“There must be a better way.”_ 😄

**MarkForge is an open-source project by Punctiq.**  
**Concept and implementation led by Alexandru Raul.**

---

## 🖼️ Screenshots

![MarkForge main UI](docs/assets/markforge-main-ui.png)

---

![MarkForge batch UI](docs/assets/markforge-batch-ui.png)
---
![MarkForge batch UI](docs/assets/markforge-convert.png)
---
![MarkForge batch UI](docs/assets/markforge-report-ui.png)



## ✨ Features

- 📄 Convert **DOCX**, **DOC**, **ODT** and **PDF** documents to Markdown
- 📦 Export Markdown and figures as a ZIP package
- 🖼️ Preserve extracted figures and image references
- 🧠 Optional AI cleanup with selectable modes:
  - 🛡️ **Safe** — maximum preservation
  - ⚖️ **Balanced** — stronger formatting cleanup
  - 🔥 **Aggressive** — stronger cleanup for messy conversions
- 📊 AI quality report with:
  - content risk
  - structure risk
  - integrity risk
  - recommendation
- 🔢 Token usage visibility
- 🧺 Batch conversion UI
- 🧙‍♂️ Dwarf-powered conversion animation, because serious tools deserve a little joy
- 🐳 Docker-friendly self-hosted workflow

---

## 🧭 What MarkForge does

MarkForge follows a simple but careful flow:

```text
Document upload
  -> deterministic conversion
  -> optional AI cleanup
  -> deterministic comparison
  -> optional AI quality audit
  -> Markdown preview
  -> ZIP export with figures and reports
```

When **AI cleanup is OFF**:

```text
convert only
  -> deterministic report only
  -> no AI call
  -> no token usage
```

When **AI cleanup is ON**:

```text
convert
  -> cleanup selected mode
  -> deterministic comparison
  -> AI quality report
  -> show report in UI
  -> include report in ZIP
```

---

## 🚀 Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make run
```

Then open:

```text
http://localhost:5000
```

---

## 🐳 Docker

```bash
docker compose up -d --build
```

Then open:

```text
http://localhost:5000
```

> 📝 Docker support may depend on your local `Dockerfile` / `docker-compose.yml` setup.

---

## 🧠 AI cleanup

AI cleanup is optional. If disabled, MarkForge performs deterministic conversion only.

Supported modes:

| Mode | Purpose | Risk |
|---|---|---|
| 🛡️ Safe | Preserve as much as possible, remove only obvious artefacts | Lowest |
| ⚖️ Balanced | Improve Markdown readability while preserving content | Medium-low |
| 🔥 Aggressive | Stronger cleanup for messy conversions | Higher, review recommended |

The AI is treated as an assistant, not as the owner of the document.

MarkForge validates AI output and rejects suspicious cleanup results when content appears to be missing, images are changed, headings are heavily reduced, or Markdown structure looks broken.

---

## 📊 Quality report

MarkForge generates a quality report to help you understand what changed.

The report can include:

- 🧾 word count before/after
- 🖼️ image reference checks
- 🧱 heading structure checks
- 📋 table line checks
- 🧠 AI audit summary
- ⚠️ possible missing content
- 🔀 possible reordered content
- ✍️ possible grammar/text rewrites
- ✅ recommendation

Generated ZIP files may include:

```text
markforge-quality-report.json
markforge-quality-report.md
```

---

## 🔐 API keys and privacy

For self-hosted usage, API keys should be provided through environment variables or a future BYOK workflow.

Never commit real secrets.

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=
```

Recommended rule:

```text
.env stays local.
.env.example goes public.
```

---

## 🤖 Supported / planned AI providers

Current and planned provider model:

- ✅ OpenAI
- ✅ Anthropic
- ✅ Groq
- ✅ OpenAI-compatible endpoints
- 🧪 xAI / Grok
- ⚠️ GitHub Copilot is not treated as a standard direct LLM API provider

---

## Optional personal Google login

MarkForge can be locked down for personal use with Google OAuth / OpenID Connect. It is disabled by default and does not add password login, registration, roles, billing, or a user database.

Set these environment variables:

```env
AUTH_ENABLED=true
AUTH_ALLOWED_EMAILS=you@example.com
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:5000/auth/callback
SECRET_KEY=use-a-long-random-secret-at-least-32-characters
SESSION_COOKIE_SECURE=false
```

Use `SESSION_COOKIE_SECURE=true` behind HTTPS in production. When auth is enabled, `/`, `/api/v1/convert`, and `/api/v1/ai/status` require a logged-in allowlisted Google account. `/api/v1/health` remains public for liveness checks.

## 🧪 Development

```bash
python -m compileall app
make run
```

If you change the UI, hard refresh your browser:

```text
Ctrl + Shift + R
```

---

## 🛡️ Disclaimer

AI cleanup and quality reports are assistive.

Always review generated Markdown before using it in production documentation, customer-facing deliverables, compliance workflows, or knowledge bases.

The dwarf is brave, but he is not legally responsible for your documentation. 🧙‍♂️⛏️

---

## 🧑‍🏭 Credits

**MarkForge is an open-source project by Punctiq.**  
**Concept and implementation led by Alexandru Raul.** 
Assisted by AI and a very determined dwarf. 🧙‍♂️⛏️💎

---

## 📜 License

Licensed under the **Apache License 2.0**.
