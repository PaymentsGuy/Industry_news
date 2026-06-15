import pytest

from intel.llm_provider import (
    MissingProviderCredential,
    extract_assistant_text,
    perplexity_chat_completion,
)


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_missing_perplexity_api_key_fails_before_network_call():
    fake_session = FakeSession({})

    with pytest.raises(MissingProviderCredential, match="PERPLEXITY_API_KEY"):
        perplexity_chat_completion(
            messages=[{"role": "user", "content": "hello"}],
            model="sonar",
            env={},
            session=fake_session,
        )

    assert fake_session.calls == []


def test_perplexity_chat_completion_extracts_assistant_text_from_fake_response():
    fake_session = FakeSession(
        {"choices": [{"message": {"content": "assistant answer"}}]}
    )

    text = perplexity_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        model="sonar",
        env={"PERPLEXITY_API_KEY": "test-key"},
        session=fake_session,
    )

    assert text == "assistant answer"
    assert len(fake_session.calls) == 1
    url, kwargs = fake_session.calls[0]
    assert url == "https://api.perplexity.ai/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "sonar"
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "hello"}]


def test_extract_assistant_text_rejects_unexpected_response_shape():
    with pytest.raises(ValueError, match="assistant message content"):
        extract_assistant_text({"choices": []})
