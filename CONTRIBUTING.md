cat > CONTRIBUTING.md <<'MD'
# 🤝 Contributing to MarkForge

Thank you for your interest in contributing to MarkForge! 🧙‍♂️⛏️

MarkForge is a self-hosted document conversion forge for turning DOCX, DOC, ODT and PDF files into clean Markdown packages with figures, optional AI cleanup, token visibility and quality reporting.

This project is human-led and AI-assisted.

**MarkForge is an open-source project by Punctiq.**  
**Concept and implementation led by Alexandru Raul.**

---

## 📌 Contribution model

MarkForge uses a simple contribution model:

```text
external contributor
  -> fork repository
  -> create branch in fork
  -> open pull request into Punctiq/markforge:develop
```

Please do **not** open pull requests directly against `main` unless it is a critical hotfix.

---

## 🌿 Branching model

The repository uses:

```text
main       stable public release branch
develop    integration branch for the next version
feature/*  new features
fix/*      bug fixes
docs/*     documentation changes
ci/*       CI/CD and repository automation
chore/*    maintenance changes
```

Examples:

```text
feature/byok-ai-settings
feature/xai-grok-provider
fix/pdf-heading-detection
fix/pdf-readable-markdown
docs/add-screenshots
ci/github-actions-validation
chore/update-dependencies
```

---

## 🔄 Pull request target

Most pull requests should target:

```text
develop
```

The `main` branch is reserved for stable releases and version tags.

Expected flow:

```text
feature/* or fix/*
  -> develop
  -> main
  -> release tag
```

---

## 🧪 Before opening a pull request

Run at least:

```bash
python -m compileall app
```

If you changed frontend behavior in `app/templates/index.html`, also do a browser smoke test.

Recommended smoke test:

1. Start the app:

```bash
make run
```

2. Open:

```text
http://localhost:5000
```

3. Test:

- Convert a small DOCX with **AI cleanup OFF**
- Convert a small DOCX with **AI cleanup ON** using `safe` mode
- Confirm Markdown preview works
- Confirm ZIP download works
- Confirm figures are included
- Confirm quality report appears
- Confirm token usage appears when available
- Confirm cancel conversion works
- Confirm API and Batch views still open

---

## 🧠 AI-assisted contributions

AI-assisted contributions are welcome, but please be transparent.

If you used AI tools, mention it in the pull request body.

Example:

```text
Human: architecture, edge cases and final review
AI-assisted: initial implementation and refactoring suggestions
```

AI tools may help with:

- boilerplate
- refactoring
- debugging
- documentation
- test ideas
- prompt engineering

AI-generated code must still be reviewed, tested and understood by the contributor.

---

## 🛡️ Document preservation rules

MarkForge is a document conversion tool, not a creative rewriting engine.

Changes must respect the core promise:

```text
Preserve the document first.
Make it prettier only when safe.
```

AI cleanup must never intentionally:

- summarize document content
- remove technical details
- invent new content
- move images
- corrupt tables
- rewrite technical meaning
- reorder sections without a clear reason
- change code blocks, commands, paths, IDs or acronyms

When in doubt, preserve the original Markdown.

---

## 📊 Quality report expectations

If your change affects conversion, AI cleanup or Markdown structure, make sure the quality report remains meaningful.

Quality reports should include or preserve:

- overall risk
- content risk
- structure risk
- integrity risk
- recommendation
- word count before/after
- retention ratio
- image count before/after
- heading count before/after
- table line count before/after
- deterministic findings
- AI audit summary when AI cleanup is enabled

Important expectations:

- If heading count changes, structure risk should be at least `medium`.
- If image references change, integrity risk should be `high`.
- If word retention drops significantly, content risk should be `high`.
- If risk is not `low`, recommendation should not be plain `accept`.

---

## 🔐 Security and privacy

Never commit:

- `.env`
- API keys
- customer documents
- private generated Markdown
- generated ZIP files
- logs
- local temporary files
- `.venv`
- `__pycache__`
- `.pyc` files

Before pushing, run:

```bash
grep -RIn \
  --exclude=.env \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  "sk-\|xai-\|OPENAI_API_KEY\|ANTHROPIC_API_KEY\|GROQ_API_KEY\|LLM_API_KEY=.*[A-Za-z0-9]\|api_key\|secret" .
```

If you find a real secret, stop and remove it before committing.

---

## 📝 Commit message convention

Please use Conventional Commits where possible:

```text
feat: add new feature
fix: fix a bug
docs: update documentation
ci: update CI workflow
refactor: restructure code without behavior change
test: add or update tests
chore: maintenance work
```

Examples:

```text
feat(pdf): add readable markdown extraction mode
fix(cleaner): preserve token usage in full document cleanup
docs: add screenshots to README
ci: add Python compile workflow
chore: update dependencies
```

---

## ✅ Pull request checklist

Before opening a PR, check:

- [ ] My branch is based on `develop`
- [ ] PR targets `develop`
- [ ] `python -m compileall app` passes
- [ ] I performed a smoke test if UI or conversion behavior changed
- [ ] I did not commit secrets or private files
- [ ] README / docs were updated if behavior changed
- [ ] AI-assisted work is disclosed if applicable
- [ ] The change preserves document content and image references

---

## 🧙‍♂️ Final note

The dwarf may swing the pickaxe, but the mine plan belongs to the human.

When in doubt, preserve the document. ⛏️💎
MD