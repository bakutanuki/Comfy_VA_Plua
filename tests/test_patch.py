import types

import pytest

import fake_va
from vaplus import patch
from vaplus.config import FALLBACK_MODEL, Store
from vaplus.venice import ModelMissing

LENGTH_NOTE = "\n\n*(That ran long and got cut off. Say \"continue\" for the rest.)*"


class FakeClient:
    instances = []

    def __init__(self, key, replies=None):
        self.key, self.bodies = key, []
        self.replies = list(replies or [])
        FakeClient.instances.append(self)

    def chat(self, body, timeout=60):
        self.bodies.append(body)
        self.timeouts = getattr(self, "timeouts", []) + [timeout]
        r = self.replies.pop(0) if self.replies else {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}
        if isinstance(r, Exception):
            raise r
        return r


def factory(*replies):
    FakeClient.instances.clear()
    return lambda key: FakeClient(key, replies)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VENICE_API_KEY", raising=False)
    patch.ORIGINALS.clear()
    store = Store(tmp_path)
    m = fake_va.make()
    return store, m, {m.__name__: m}


def patched(env, *replies, key="k"):
    store, m, mods = env
    if key:
        store.set_key(key)
    assert patch.ensure_patched(store, factory(*replies), modules=mods) == "patched"
    return store, m


def test_find_via_mappings(env):
    _, m, mods = env
    cls = type("LCVisionLoader", (), {"__module__": "ComfyUI_LC_Vision_nodes.lc_vision_loader"})
    assert patch.find_va(mods, {"LCVisionLoader": cls}) is m


def test_find_via_scan(env):
    _, m, _ = env
    mods = {"x.y": types.ModuleType("x.y"), "custom.ComfyUI_LC_Vision_nodes.lc_vision_assistant": m}
    assert patch.find_va(mods, {}) is m
    assert patch.find_va({"z": types.ModuleType("z")}, {}) is None


def test_missing(env):
    store, _, _ = env
    assert patch.ensure_patched(store, factory(), modules={}) == "missing"


def test_fail_closed_when_names_missing(env):
    store, m, mods = env
    del m._salvage
    orig_chat = m._chat
    assert patch.ensure_patched(store, factory(), modules=mods) == "changed"
    assert m._chat is orig_chat


def test_idempotent(env):
    store, m = patched(env)
    wrapper = m._chat
    assert patch.ensure_patched(store, factory(), modules={m.__name__: m}) == "already"
    assert m._chat is wrapper


def test_routes_local_without_key(env):
    store, m = patched(env, key=None)
    assert m._chat([{"role": "user", "content": "x"}], "ctx", "auto") == ("local reply", [])
    assert ("chat", "auto") in m.calls


def test_local_choice_wins(env):
    store, m = patched(env)
    m._chat([{"role": "user", "content": "x"}], "ctx", "Qwen3-VL-4B Q4_K_M")
    assert ("chat", "Qwen3-VL-4B Q4_K_M") in m.calls
    assert all(not c.bodies for c in FakeClient.instances)


def test_off_wins(env):
    store, m = patched(env)
    assert m._plan("off")["mode"] == "gpu"


def test_disabled_routes_local(env):
    store, m = patched(env)
    store.save({"enabled": False})
    assert m._chat([{"role": "user", "content": "x"}], "ctx", "auto")[0] == "local reply"


def test_chat_via_venice(env):
    reply = {"choices": [{"message": {"content": 'Here.\n```actions\n[{"do":"highlight","nodes":[3]}]\n```'},
                          "finish_reason": "length"}], "_cost_usd": 0.01}
    store, m = patched(env, reply)
    turns = [{"role": "tool", "content": "skip"}] + [{"role": "user", "content": "q" * 5000}] * 14
    text, actions = m._chat(turns, "WORKFLOW CTX", "auto")
    assert text == "Here." + LENGTH_NOTE and actions == [{"do": "highlight", "nodes": [3]}]
    body = FakeClient.instances[-1].bodies[0]
    sys_msg = body["messages"][0]["content"]
    assert sys_msg.startswith(m.SYSTEM) and patch.VAPLUS_ADDENDUM in sys_msg and "WORKFLOW CTX" in sys_msg
    assert len(body["messages"]) == 1 + 12 and all(len(t["content"]) <= 4000 for t in body["messages"][1:])
    assert body["model"] == store.load()["model"]
    assert patch.SESSION["cost_usd"] >= 0.01


def test_model_fallback(env):
    store, m = patched(env, ModelMissing("gone"), {"choices": [{"message": {"content": "ok"}}]})
    assert m._chat([{"role": "user", "content": "x"}], "", "auto")[0] == "ok"
    assert FakeClient.instances[-1].bodies[1]["model"] == FALLBACK_MODEL
    assert "fallback" in patch.SESSION["status"].lower()


def test_tour_via_venice(env):
    store, m = patched(env, {"choices": [{"message": {"content": '{"title": "T", "steps": []}'}}]})
    assert m._tour("P1 ...", "summary", "auto") == {"title": "T", "steps": []}
    body = FakeClient.instances[-1].bodies[0]
    assert body["messages"][1]["content"].startswith("PARTS:\nP1 ...") and body["response_format"]["json_schema"]["strict"]
    assert FakeClient.instances[-1].timeouts == [150]


def test_tour_salvage_fallback(env):
    store, m = patched(env, {"choices": [{"message": {"content": '{"title": "T", "steps": [{"parts": ['}}]})
    assert m._tour("P1", "", "auto") == {"title": "salvaged", "steps": []}


def test_plan_cloud(env):
    store, m = patched(env)
    assert m._plan(None) == patch.cloud_plan(store, 10.0)
    assert patch.cloud_plan(store, 10.0)["tours"] is True and patch.cloud_plan(store, 10.0)["mode"] == "cloud"


def test_use_venice_rule(env):
    store, _, _ = env
    assert not patch.use_venice(store, "auto", [])
    store.set_key("k")
    assert patch.use_venice(store, "auto", []) and patch.use_venice(store, None, [])
    assert not patch.use_venice(store, "off", []) and not patch.use_venice(store, "local", ["local"])
