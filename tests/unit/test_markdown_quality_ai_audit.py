from app.agent.base_llm import LLMError
from app.quality import markdown_quality as mq


class _FailingClient:
    last_usage = {}

    def __init__(self, message):
        self.message = message

    def complete(self, **kwargs):
        raise LLMError(self.message)


class _SuccessfulClient:
    last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def complete(self, **kwargs):
        return """{
  "risk_level": "low",
  "recommendation": "accept",
  "summary": "No obvious issue detected.",
  "possible_missing_content": [],
  "possible_reordered_content": [],
  "grammar_text_changes": [],
  "formatting_changes": [],
  "integrity_concerns": []
}"""


def _report_config(**overrides):
    config = {
        "LLM_API_KEY": "test-key",
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "test-model",
    }
    config.update(overrides)
    return config


def test_context_length_error_detection_is_case_insensitive():
    assert mq._is_context_length_error("CONTEXT_LENGTH_EXCEEDED from provider")


def test_context_length_error_detects_prompt_too_long():
    assert mq._is_context_length_error("BadRequest: prompt is too long for this model")


def test_context_length_error_detects_maximum_context_length():
    assert mq._is_context_length_error("This model's maximum context length is 8192 tokens")


def test_invalid_ai_quality_config_values_fall_back(monkeypatch):
    monkeypatch.setattr(mq, "get_llm_client", lambda config: _SuccessfulClient())

    report = mq.build_quality_report(
        original_markdown="# Title\n\nOriginal body",
        final_markdown="# Title\n\nOriginal body",
        mode="safe",
        ai_cleanup_requested=True,
        ai_applied=True,
        config=_report_config(
            AI_QUALITY_SAFE_INPUT_TOKENS="not-a-number",
            AI_QUALITY_MAX_OUTPUT_TOKENS=-10,
            AI_QUALITY_SAMPLE_CHARS=None,
        ),
    )

    assert report["deterministic_report"]["enabled"] is True
    assert report["ai_report_error"] is None
    assert report["ai_report"]["summary"] == "No obvious issue detected."


def test_unexpected_ai_audit_exception_returns_deterministic_report(monkeypatch, caplog):
    raw_error = "provider exploded with secret raw details"

    def fail_audit(**kwargs):
        raise RuntimeError(raw_error)

    monkeypatch.setattr(mq, "_ai_quality_report", fail_audit)

    report = mq.build_quality_report(
        original_markdown="# Title\n\nOriginal body",
        final_markdown="# Title\n\nOriginal body",
        mode="safe",
        ai_cleanup_requested=True,
        ai_applied=True,
        config=_report_config(),
    )

    assert report["deterministic_report"]["enabled"] is True
    assert report["ai_report"] is None
    assert report["ai_report_error"] == mq._AI_AUDIT_FAILED_MESSAGE
    assert raw_error not in str(report)
    assert raw_error not in mq.build_quality_report_markdown(report)
    assert raw_error in caplog.text


def test_provider_context_error_is_sanitized(monkeypatch, caplog):
    raw_error = "CONTEXT_LENGTH_EXCEEDED: raw provider details and request id abc123"
    monkeypatch.setattr(mq, "get_llm_client", lambda config: _FailingClient(raw_error))

    report = mq.build_quality_report(
        original_markdown="# Title\n\nOriginal body",
        final_markdown="# Title\n\nOriginal body",
        mode="safe",
        ai_cleanup_requested=True,
        ai_applied=True,
        config=_report_config(),
    )

    assert report["ai_report"] is None
    assert report["ai_report_error"] == mq._AI_AUDIT_TOO_LARGE_MESSAGE
    assert "raw provider details" not in str(report)
    assert "abc123" not in str(report)
    assert "raw provider details" not in mq.build_quality_report_markdown(report)
    assert "abc123" not in mq.build_quality_report_markdown(report)
    assert raw_error in caplog.text
