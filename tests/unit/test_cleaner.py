import app.agent.cleaner as cleaner_module
from app.agent.base_llm import LLMError
from app.agent.cleaner import MarkdownCleaner


BASE_CONFIG = {
    "LLM_API_KEY": "test-key",
    "LLM_PROVIDER": "openai",
    "LLM_MODEL": "test-model",
}


def _markdown_from_prompt(prompt: str) -> str:
    start = "--- MARKDOWN START ---"
    end = "--- MARKDOWN END ---"
    return prompt.split(start, 1)[1].split(end, 1)[0].strip()


def _cleanup_response(markdown: str) -> str:
    return f'{markdown}\n```json\n{{"fixes": []}}\n```'


class EchoClient:
    def __init__(self):
        self.calls = []
        self.last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        self.calls.append(user)
        return _cleanup_response(_markdown_from_prompt(user))


class FailingFirstChunkClient(EchoClient):
    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        self.calls.append(user)
        if len(self.calls) == 1:
            raise LLMError("provider exploded with secret endpoint https://internal.example")
        return _cleanup_response(_markdown_from_prompt(user))


def _install_client(monkeypatch, client):
    monkeypatch.setattr(cleaner_module, "get_llm_client", lambda config: client)
    return client


def test_invalid_full_cleanup_char_config_does_not_crash(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {**BASE_CONFIG, "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP": "not-an-int"}

    result = MarkdownCleaner(config=config).clean("# Title\n\nBody text")

    assert result.markdown == "# Title\n\nBody text"
    assert result.ai_applied is True
    assert len(client.calls) == 1


def test_invalid_chunk_char_config_does_not_crash(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {**BASE_CONFIG, "LLM_MAX_MARKDOWN_CHARS_PER_CHUNK": "bad-value"}
    markdown = "\n\n".join(f"# Section {idx}\n" + ("word " * 800) for idx in range(8))

    result = MarkdownCleaner(config=config).clean(markdown)

    assert result.markdown
    assert isinstance(result.fixes, list)
    assert isinstance(result.token_usage, dict)
    assert len(client.calls) > 1


def test_invalid_cleanup_token_budget_config_does_not_crash(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {
        **BASE_CONFIG,
        "LLM_MAX_OUTPUT_TOKENS": "not-a-number",
        "LLM_CLEANUP_CONTEXT_WINDOW_TOKENS": "-1",
    }

    result = MarkdownCleaner(config=config).clean("# Title\n\nBody")

    assert result.markdown == "# Title\n\nBody"
    assert isinstance(result.token_usage, dict)
    assert len(client.calls) == 1


def test_oversized_full_cleanup_switches_to_chunked(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {
        **BASE_CONFIG,
        "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP": "200000",
        "LLM_CLEANUP_CONTEXT_WINDOW_TOKENS": "6000",
        "LLM_MAX_OUTPUT_TOKENS": "1000",
    }
    markdown = "\n\n".join(f"# Section {idx}\n" + ("word " * 500) for idx in range(6))

    result = MarkdownCleaner(config=config).clean(markdown)

    assert result.markdown
    assert len(client.calls) > 1
    assert result.ai_applied is True


def test_oversized_chunk_is_skipped_before_provider_call(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {
        **BASE_CONFIG,
        "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP": "1000",
        "LLM_MAX_MARKDOWN_CHARS_PER_CHUNK": "1000",
        "LLM_CLEANUP_CONTEXT_WINDOW_TOKENS": "2304",
        "LLM_MAX_OUTPUT_TOKENS": "10000",
    }
    cleaner = MarkdownCleaner(config=config)
    cleaner.system_prompt = "x" * 6000
    markdown = "# Huge\n\n" + ("a" * 5000)

    result = cleaner.clean(markdown)

    assert result.markdown == markdown
    assert result.ai_applied is False
    assert client.calls == []
    assert result.fixes == ["AI chunked cleanup did not safely apply to any chunk; original markdown kept."]


def test_dense_oversized_input_is_not_sent_to_provider(monkeypatch):
    client = _install_client(monkeypatch, EchoClient())
    config = {
        **BASE_CONFIG,
        "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP": "200000",
        "LLM_MAX_MARKDOWN_CHARS_PER_CHUNK": "5000",
        "LLM_CLEANUP_CONTEXT_WINDOW_TOKENS": "2304",
        "LLM_MAX_OUTPUT_TOKENS": "1000",
    }
    markdown = "# Dense\n\n" + ("x" * 5000)

    result = MarkdownCleaner(config=config).clean(markdown)

    assert result.markdown == markdown
    assert result.ai_applied is False
    assert client.calls == []


def test_llm_error_during_chunk_cleanup_preserves_original_and_sanitizes(monkeypatch):
    client = _install_client(monkeypatch, FailingFirstChunkClient())
    config = {
        **BASE_CONFIG,
        "LLM_MAX_MARKDOWN_CHARS_FOR_FULL_CLEANUP": "1000",
        "LLM_MAX_MARKDOWN_CHARS_PER_CHUNK": "3000",
    }
    markdown = "# First\n\n" + ("alpha " * 900) + "\n\n# Second\n\n" + ("beta " * 900)

    result = MarkdownCleaner(config=config).clean(markdown)

    assert "# First" in result.markdown
    assert "# Second" in result.markdown
    assert result.ai_applied is True
    assert len(client.calls) >= 2
    visible = " ".join(result.fixes)
    assert "provider exploded" not in visible
    assert "internal.example" not in visible
    assert "AI cleanup failed for one chunk; original Markdown was preserved." in visible


def test_unexpected_exception_during_cleanup_preserves_original(monkeypatch):
    monkeypatch.setattr(cleaner_module, "get_llm_client", lambda config: (_ for _ in ()).throw(RuntimeError("raw boom")))
    markdown = "# Title\n\nBody"

    result = MarkdownCleaner(config=BASE_CONFIG).clean(markdown)

    assert result.markdown == markdown
    assert result.ai_applied is False
    assert result.fixes == ["AI cleanup failed; original Markdown was preserved."]


def test_full_document_llm_error_uses_sanitized_user_visible_fix(monkeypatch):
    class FailingClient(EchoClient):
        def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
            raise LLMError("raw provider stack with api.example")

    _install_client(monkeypatch, FailingClient())
    markdown = "# Title\n\nBody"

    result = MarkdownCleaner(config=BASE_CONFIG).clean(markdown)

    assert result.markdown == markdown
    assert result.ai_applied is False
    assert result.fixes == ["AI cleanup failed; original Markdown was preserved."]
    assert "api.example" not in " ".join(result.fixes)


def test_cleanup_result_shape_remains_stable(monkeypatch):
    _install_client(monkeypatch, EchoClient())

    result = MarkdownCleaner(config=BASE_CONFIG).clean("# Title\n\nBody")

    assert isinstance(result.markdown, str)
    assert isinstance(result.fixes, list)
    assert isinstance(result.ai_applied, bool)
    assert set(result.token_usage) == {"prompt_tokens", "completion_tokens", "total_tokens", "llm_calls"}
