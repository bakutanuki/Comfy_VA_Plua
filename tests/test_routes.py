import asyncio
import json

from vaplus import routes
from vaplus.config import Store


class Req:
    def __init__(self, body=None, query=None):
        self._body, self.query = body, query or {}

    async def json(self):
        return self._body


def run(coro):
    return asyncio.run(coro)


def test_rewrite_status_on():
    out = routes.rewrite_status({"available": False, "why": "llama-cpp missing", "models": []}, True)
    assert out["available"] is True and out["why"] == ""


def test_rewrite_status_off():
    payload = {"available": False, "why": "x"}
    assert routes.rewrite_status(dict(payload), False) == payload


def test_key_endpoint_never_returns_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VENICE_API_KEY", raising=False)
    store = Store(tmp_path)
    resp = run(routes.post_key(store, Req({"key": "super-secret"})))
    assert "super-secret" not in resp.text and json.loads(resp.text) == {"ok": True, "has_key": True}
    assert store.get_key() == "super-secret"


def test_config_endpoint_validates(tmp_path):
    store = Store(tmp_path)
    resp = run(routes.post_config(store, Req({"enabled": False, "evil": "x"})))
    assert json.loads(resp.text)["enabled"] is False and "evil" not in resp.text
    assert run(routes.post_config(store, Req(["not", "a", "dict"]))).status == 400


def test_models_without_key_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("VENICE_API_KEY", raising=False)
    assert json.loads(run(routes.get_models(Store(tmp_path))).text) == []


def test_models_filtered():
    data = [{"id": "a", "model_spec": {"name": "A", "capabilities": {"supportsFunctionCalling": True},
                                        "pricing": {"input": {"usd": 0.3}, "output": {"usd": 1.2}}}},
            {"id": "b", "model_spec": {"capabilities": {}}}]
    assert routes.summarize_models(data) == [{"id": "a", "name": "A", "price_in": 0.3, "price_out": 1.2}]
