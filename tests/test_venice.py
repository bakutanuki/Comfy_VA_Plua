import io
import json
import urllib.error

import pytest

from vaplus import venice
from vaplus.venice import Client, VeniceError, build_chat_body, build_tour_body, reply_text, strictify

VP = {"include_venice_system_prompt": False, "enable_web_search": "off"}
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "steps": {"type": "array", "items": {
    "type": "object", "properties": {"text": {"type": "string"}, "settings": {"type": "array", "items": {
        "type": "object", "properties": {"node": {"type": "string"}, "why": {"type": "string"}}, "required": ["node"]}}},
    "required": ["text"]}}}, "required": ["title"]}


class Resp(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(json.dumps(data).encode())
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b'{"error":"x"}'))


class Opener:
    def __init__(self, *outcomes):
        self.outcomes, self.requests = list(outcomes), []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return Resp(o)


def test_chat_body_shape():
    b = build_chat_body("m", "SYS", [{"role": "user", "content": "hi"}])
    assert b["venice_parameters"] == VP
    assert b["reasoning_effort"] == "low" and b["temperature"] == 0.3 and b["max_completion_tokens"] == 4000
    assert b["messages"][0] == {"role": "system", "content": "SYS"} and b["messages"][1]["content"] == "hi"
    assert "repeat_penalty" not in b and "top_k" not in b and b["model"] == "m"


def test_tour_body_uses_strict_schema():
    b = build_tour_body("m", "S", "U", SCHEMA)
    assert b["response_format"] == {"type": "json_schema", "json_schema": {"name": "tour", "strict": True, "schema": strictify(SCHEMA)}}
    assert b["venice_parameters"] == VP


def test_strictify_nested():
    s = strictify(SCHEMA)
    inner = s["properties"]["steps"]["items"]["properties"]["settings"]["items"]
    assert s["additionalProperties"] is False and inner["additionalProperties"] is False
    assert sorted(inner["required"]) == ["node", "why"]
    assert SCHEMA["properties"]["steps"]["items"]["properties"]["settings"]["items"]["required"] == ["node"]  # no mutation


@pytest.mark.parametrize("code,msg", [
    (401, "Your Venice key was rejected. Set it again in Settings > Vision Plus."),
    (402, "Your Venice balance is empty."),
    (429, "Venice is rate-limiting you. Wait a minute."),
])
def test_error_messages(code, msg):
    with pytest.raises(VeniceError, match="^" + msg.replace(".", r"\.") + "$"):
        Client("k", opener=Opener(http_error(code))).chat({})


def test_5xx_twice_message():
    with pytest.raises(VeniceError, match="Venice didn't answer. Try again."):
        Client("k", opener=Opener(http_error(500), http_error(500))).chat({})


def test_no_retry_on_4xx():
    op = Opener(http_error(400))
    with pytest.raises(VeniceError):
        Client("k", opener=op).chat({})
    assert len(op.requests) == 1
    op = Opener(http_error(503), {"choices": []})
    assert Client("k", opener=op).chat({})["choices"] == []
    assert len(op.requests) == 2


def test_404_raises_model_missing():
    with pytest.raises(venice.ModelMissing):
        Client("k", opener=Opener(http_error(404))).chat({})


def test_key_only_in_header():
    op = Opener({"choices": []})
    Client("secret-k", opener=op).chat({"model": "m"})
    r = op.requests[0]
    assert r.get_header("Authorization") == "Bearer secret-k"
    assert "secret-k" not in r.full_url and r.full_url.endswith("/chat/completions")


def test_cost_extracted():
    op = Opener({"choices": [], "usage": {"cost": {"usd": 0.0042}}})
    assert Client("k", opener=op).chat({})["_cost_usd"] == pytest.approx(0.0042)


def test_strip_and_length_note():
    resp = {"choices": [{"message": {"content": "<think>hmm</think>\nHello"}, "finish_reason": "length"}]}
    assert reply_text(resp) == ("Hello", True)
    assert reply_text({"choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}]}) == ("Hi", False)
