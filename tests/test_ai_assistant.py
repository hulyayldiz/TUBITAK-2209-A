"""Tests for local, general-purpose Ollama chat behavior."""

import ai_assistant as assistant


class FakeResponse:
    ok = True
    status_code = 200

    @staticmethod
    def json():
        return {"message": {"role": "assistant", "content": "A black hole bends spacetime."}}


def test_chat_sends_multi_turn_history_only_to_local_model(monkeypatch):
    request = {}

    def fake_post(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    history = [
        {"role": "assistant", "content": assistant.INITIAL_GREETING},
        {"role": "user", "content": "Merhaba"},
        {"role": "assistant", "content": "Merhaba!"},
        {"role": "user", "content": "Kara delik nedir?"},
    ]

    answer = assistant.ask_local_model("Kara delik nedir?", history=history)

    assert answer == "A black hole bends spacetime."
    assert request["url"] == assistant.CHAT_URL
    messages = request["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert [item["role"] for item in messages[1:]] == ["user", "assistant", "user"]
    assert "general-purpose AI assistant" in messages[0]["content"]
    assert "Uygulama durumu:" not in messages[0]["content"]
    assert request["json"]["model"] == assistant.OLLAMA_MODEL
    assert request["json"]["stream"] is False
    assert "x-goog-api-key" not in request.get("headers", {})


def test_runtime_context_is_only_attached_to_status_questions(monkeypatch):
    request = {}

    def fake_post(url, **kwargs):
        request.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    state = {"use_dataset_mode": True, "true_lat": 38.1, "true_lon": 39.2,
             "current_detector_decision": "NORMAL", "current_speed": 12.5}
    assistant.ask_local_model(
        "Uygulama durumu nedir?", state,
        history=[{"role": "user", "content": "Uygulama durumu nedir?"}],
    )
    instruction = request["json"]["messages"][0]["content"]
    assert "kaynak=yüklenen kayıt oynatımı" in instruction
    assert "38.10000, 39.20000" in instruction
    assert "saldırı kanıtı değildir" in instruction


def test_missing_local_service_returns_setup_help(monkeypatch):
    def unavailable(*args, **kwargs):
        raise assistant.requests.ConnectionError

    monkeypatch.setattr(assistant.requests, "post", unavailable)

    reply = assistant.ask_local_model("Kara delik nedir?", history=[])

    assert "Yerel Ollama servisine bağlanamadım" in reply
    assert assistant.OLLAMA_MODEL in reply
