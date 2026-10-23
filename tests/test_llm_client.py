import llm_client


def test_reasoning_model_params():
    payload = {}
    llm_client._apply_model_params(payload, "gpt-6-luna", 0.2, 256)
    assert payload["reasoning_effort"] == "low"
    assert payload["max_completion_tokens"] >= 4096       # room for reasoning tokens
    assert "temperature" not in payload and "max_tokens" not in payload

    payload = {}
    llm_client._apply_model_params(payload, "gpt-6-luna", 0.0, 2048, effort="none")
    assert payload == {"reasoning_effort": "none", "max_completion_tokens": 2048, "temperature": 0.0}


def test_classic_model_params():
    payload = {}
    llm_client._apply_model_params(payload, "gpt-4o", 0.2, 1024)
    assert payload == {"temperature": 0.2, "max_tokens": 1024}


class _Resp:
    status_code = 200
    text = '{"choices":[{"message":{"content":"ok"}}]}'

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


def test_language_directive_and_no_thinking_field(monkeypatch):
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.update(json)
        return _Resp()

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    assert llm_client.call_llm("SYS", "USER", model="gpt-4o", enable_thinking=True) == "ok"
    assert "Output Language" in sent["messages"][0]["content"]
    assert "chat_template_kwargs" not in sent


def test_client_errors_fail_fast(monkeypatch):
    class Bad(_Resp):
        status_code = 400
        text = '{"error": "unsupported parameter"}'

    calls = []
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: calls.append(1) or Bad())
    try:
        llm_client.call_llm("s", "u", model="gpt-4o")
    except llm_client.LLMRequestError as e:
        assert "unsupported parameter" in str(e)
    assert len(calls) == 1
