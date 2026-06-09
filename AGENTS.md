# 🤖 AGENTS.md — MarkForge Coding Agent Guide

MarkForge is a self-hosted document conversion forge for turning DOCX, DOC, ODT and PDF files into clean Markdown packages with figures, optional AI cleanup, token usage tracking and quality reporting.

Concept and implementation led by **Alexandru Raul**.
Assisted by AI coding agents and a very determined documentation dwarf. 🧙‍♂️⛏️

This file is for coding agents working in this repository. Keep it practical. Prefer small, safe, reviewable changes.

---

## Core rules

* Fix the root cause, not only the visible symptom.
* Prefer small PR-sized changes.
* Keep the app runnable after every meaningful change.
* Do not overwrite working code with older versions.
* If existing code looks intentional, preserve it unless the requested change clearly requires otherwise.
* If unsure, inspect more files before changing code.
* Do not add large new dependencies without checking license and necessity.
* Never commit secrets, API keys, customer documents, generated ZIPs, logs or private test files.
* Preserve the MarkForge identity: self-hosted, practical, technical, slightly fun.

---

## Important paths

* `app/templates/index.html` — main UI, API view, Batch view, status panels.
* `app/api/v1/convert.py` — conversion and AI status API routes.
* `app/services/conversion_service.py` — conversion orchestration.
* `app/converters/` — document converters.
* `app/builders/markdown_builder.py` — Markdown assembly.
* `app/builders/frontmatter.py` — frontmatter generation.
* `app/builders/zip_builder.py` — ZIP packaging.
* `app/agent/cleaner.py` — AI cleanup pipeline.
* `app/agent/prompts.py` — AI cleanup prompts.
* `app/agent/openai_llm.py` — OpenAI-compatible client.
* `app/agent/anthropic_llm.py` — Anthropic client.
* `app/agent/llm_registry.py` — LLM provider selection.
* `app/quality/markdown_quality.py` — deterministic and AI quality reporting.
* `.env.example` — public environment template.
* `README.md` — public user documentation.

---

## Local development

Use Python 3.12 if available.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make run
```

Open:

```text
http://localhost:5000
```

---

## Validation

Always run before finishing Python changes:

```bash
python -m compileall app
```

If only one Python file changed:

```bash
python -m compileall app/path/to/file.py
```

If `app/templates/index.html` changed, do a browser smoke test.

Recommended smoke test:

1. Start the app with `make run`.
2. Open `http://localhost:5000`.
3. Convert a small DOCX with AI cleanup OFF.
4. Convert a small DOCX with AI cleanup ON using `safe` mode.
5. Confirm Markdown preview works.
6. Confirm ZIP download works.
7. Confirm figures are included.
8. Confirm token usage appears when available.
9. Confirm quality report appears.
10. Confirm cancel conversion still works.

---

## Expected conversion flows

When `AI cleanup` is OFF:

```text
convert
-> deterministic quality comparison
-> no LLM call
-> no token usage
-> no AI audit
```

When `AI cleanup` is ON:

```text
convert
-> cleanup selected mode
-> deterministic quality comparison
-> AI quality audit
-> show report in UI
-> include report in ZIP
```

Never call any LLM when AI cleanup is disabled.

---

## AI cleanup safety

MarkForge is a document conversion tool, not a creative rewriting engine.

AI cleanup must preserve:

* original meaning
* original language
* paragraphs
* headings
* tables
* images
* captions
* links
* lists
* code blocks
* commands
* paths
* IDs
* acronyms
* technical details

AI cleanup must not intentionally:

* summarize
* omit content
* invent content
* move images
* corrupt tables
* rewrite for style
* change technical meaning
* reorder sections without a clear reason

When in doubt, preserve the original Markdown.

---

## AI output fallback rules

Do not trust LLM output blindly.

Reject or fall back to original Markdown if AI output is:

* truncated
* too short
* missing the required JSON block
* missing image references
* reordering image references
* missing many headings
* corrupting code fences
* malformed beyond safe parsing

For `safe` mode, preservation is more important than pretty formatting.

---

## Quality report rules

Quality reports should include:

* overall risk
* content risk
* structure risk
* integrity risk
* recommendation
* word count before and after
* retention ratio
* image count before and after
* heading count before and after
* table line count before and after
* deterministic findings
* AI audit summary when available

Risk rules:

* If heading count changes, structure risk should be at least `medium`.
* If image references change, integrity risk should be `high`.
* If word retention drops significantly, content risk should be `high`.
* If risk is not `low`, recommendation should not be plain `accept`.

---

## LLM provider rules

Supported or planned provider patterns:

* OpenAI
* Anthropic
* Groq
* xAI / Grok
* Custom OpenAI-compatible endpoint

GitHub Copilot must not be treated as a normal direct LLM provider unless an official compatible API is available.

Never expose API keys in API responses, ZIP reports, logs or UI output.

---

## UI rules

The UI should feel self-hosted, practical and friendly.

Keep:

* AI status panel
* API view
* Batch view
* AI cleanup toggle
* AI mode selector
* token usage display
* quality report panel
* cancel conversion button
* dwarf-powered conversion animation

Do not reintroduce SaaS-style buttons such as:

* `Sign in`
* `Start free`

Preferred header:

```text
Self-hosted · ⛏️ Forge ready
```

Preferred footer:

```text
MarkForge · Forging Markdown from stubborn documents
Concept and implementation led by Alexandru Raul · Assisted by AI and a very determined dwarf 🧙‍♂️⛏️
```

---

## Docker rules

The app must remain Docker-friendly.

Do not bake secrets into Docker images.

Use environment variables or external secrets for:

* `LLM_PROVIDER`
* `LLM_MODEL`
* `LLM_BASE_URL`
* `LLM_API_KEY`

Future BYOK support should allow users to provide their own API key per browser session or user account.

---

## Public repository safety

Never commit:

* `.env`
* API keys
* customer documents
* private generated Markdown
* generated ZIP files
* logs
* local temporary files
* `.venv`
* `__pycache__`
* `.pyc` files

Before public commits, check for secrets:

```bash
grep -RIn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ \
  "sk-\|xai-\|OPENAI_API_KEY\|ANTHROPIC_API_KEY\|GROQ_API_KEY\|LLM_API_KEY=.*[A-Za-z0-9]\|api_key\|secret" .
```

If a secret is found, stop and ask before committing.

---

## Documentation rules

Update documentation when behavior changes.

Update `README.md` or `.env.example` when changing:

* setup
* Docker usage
* API behavior
* AI provider configuration
* AI cleanup behavior
* quality report behavior
* ZIP output contents
* security expectations

Keep README human-friendly. Keep AGENTS.md agent-focused.

---

## Commit message conventions

Use Conventional Commits when possible:

```text
feat: add PDF table extraction
fix(cleaner): preserve token usage in full document cleanup
docs: update Docker quick start
refactor(agent): centralize cleanup mode configuration
chore: prepare public repository files
```

Common types:

* `feat:` new feature
* `fix:` bug fix
* `docs:` documentation changes
* `refactor:` code restructuring
* `test:` tests
* `chore:` maintenance
* `ci:` CI configuration

---

## Pre-PR checklist

Before opening a pull request or finishing an agent task:

* [ ] `python -m compileall app` passes
* [ ] app starts with `make run`
* [ ] DOCX conversion works
* [ ] AI cleanup OFF does not call any LLM
* [ ] AI cleanup ON works with `safe` mode
* [ ] token usage appears when available
* [ ] quality report appears in UI
* [ ] ZIP contains Markdown and quality reports
* [ ] no secrets are committed
* [ ] README or `.env.example` updated if behavior changed

---

## Final rule

The dwarf may swing the pickaxe, but the mine plan belongs to the human.

When in doubt, preserve the document. ⛏️💎
