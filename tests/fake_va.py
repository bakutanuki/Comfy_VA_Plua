"""A stand-in for LC Vision's lc_vision_assistant module with the same names and signatures VA+ relies on."""
import json
import re
import types

_BLOCK = re.compile(r"```(?:actions|json)?\s*([\[{].*?[\]}])\s*```", re.S)


def make(name="ComfyUI_LC_Vision_nodes.lc_vision_assistant", local=("Qwen3-VL-4B Q4_K_M",)):
    m = types.ModuleType(name)
    m.calls = []
    m.SYSTEM = "You are Vision Assistant."
    m.TOUR_SYSTEM = "You write a guided tour."
    m.TOUR_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
    m._BLOCK = _BLOCK

    def strip_thinking(t):
        return re.sub(r"<think>.*?</think>", "", t, flags=re.S)

    def _split(out):
        actions = [json.loads(x) for x in _BLOCK.findall(out)]
        return _BLOCK.sub("", out).strip(), [a for a in (actions[0] if actions and isinstance(actions[0], list) else actions)]

    def _salvage(text):
        return {"title": "salvaged", "steps": []}

    def _discover_vision_models():
        return {n: ("path.gguf",) for n in local}

    def _chat(messages, context, requested):
        m.calls.append(("chat", requested))
        return "local reply", []

    def _tour(parts, context, requested):
        m.calls.append(("tour", requested))
        return {"title": "local", "steps": []}

    def _plan(requested=None):
        m.calls.append(("plan", requested))
        return {"name": "Qwen3-VL-4B", "path": "p", "ctx": 8192, "need_gb": 4.0, "vram_gb": 10.0, "tours": False,
                "lite": False, "mode": "gpu", "why": ""}

    for f in (strip_thinking, _split, _salvage, _discover_vision_models, _chat, _tour, _plan):
        setattr(m, f.__name__, f)
    return m
