# 🤝 Contributing to MarkForge

Contributions are welcome.

Please open an issue before large changes, especially for architecture, AI provider behavior, conversion logic, or ZIP output structure.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make run
```

## Pull requests

- Keep changes focused
- Do not commit secrets
- Do not commit customer documents
- Add tests where possible
- Update README/docs when behavior changes
- Keep AI cleanup conservative by default

## Philosophy

MarkForge should preserve document content first and improve formatting second.

The dwarf may be funny, but the conversion pipeline should be boringly reliable. 🧙‍♂️⛏️
