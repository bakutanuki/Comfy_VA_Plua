"""Find LC Vision's already-loaded lc_vision_assistant module and route its chat, tour and plan through Venice.

Only m._chat, m._tour and m._plan are replaced: VA's routes look them up as module globals at call time. Shared helpers
(_plan_for, _free, _llama_kwargs, _make_room, _discover_vision_models) stay untouched because LC Note's translator uses them.
LC Vision files are never imported by name (that would load a second copy with duplicate routes)."""
import json
import sys
import threading

from .config import FALLBACK_MODEL
from .venice import Client, ModelMissing, build_chat_body, build_tour_body, reply_text

NEEDED = ("SYSTEM", "TOUR_SYSTEM", "TOUR_SCHEMA", "_chat", "_tour", "_plan", "_split", "_salvage", "_discover_vision_models")
ORIGINALS = {}
SESSION = {"cost_usd": 0.0, "last_error": "", "status": ""}
LENGTH_NOTE = "\n\n*(That ran long and got cut off. Say \"continue\" for the rest.)*"
VAPLUS_ADDENDUM = ("VA+ NOTE: you are running as VA+ on a cloud model through Venice, so you have a long context and can give "
                   "fuller answers. Every rule above still applies.")
_LOCK = threading.Lock()


def find_va(modules=None, mappings=None):
    modules = sys.modules if modules is None else modules
    if mappings is None:
        mappings = getattr(modules.get("nodes"), "NODE_CLASS_MAPPINGS", {}) or {}
    cls = mappings.get("LCVisionLoader")
    if cls is not None:
        pkg = getattr(cls, "__module__", "").rpartition(".")[0]
        m = modules.get(pkg + ".lc_vision_assistant") if pkg else None
        if m is not None:
            return m
    for key, m in list(modules.items()):
        if key.endswith(".lc_vision_assistant") and all(hasattr(m, n) for n in ("SYSTEM", "_chat", "_tour")):
            return m
    return None


def use_venice(store, requested, local_models) -> bool:
    return bool(store.load()["enabled"] and store.has_key() and requested != "off" and requested not in local_models)


def cloud_plan(store, vram_gb: float) -> dict:
    return {"name": "Venice · " + store.load()["model"], "path": None, "ctx": 131072, "need_gb": 0.0, "vram_gb": vram_gb,
            "tours": True, "lite": False, "mode": "cloud", "why": ""}


def _call(store, client_factory, make_body, timeout=60):
    model = store.load()["model"]
    client = client_factory(store.get_key())
    try:
        resp = client.chat(make_body(model), timeout=timeout)
    except ModelMissing:
        SESSION["status"] = f"{model} is gone from Venice; using the fallback {FALLBACK_MODEL}."
        resp = client.chat(make_body(FALLBACK_MODEL), timeout=timeout)
    SESSION["cost_usd"] += resp.get("_cost_usd") or 0.0
    SESSION["last_error"] = ""
    return resp


def _wrap(m, store, client_factory):
    orig_chat, orig_tour, orig_plan = ORIGINALS["_chat"], ORIGINALS["_tour"], ORIGINALS["_plan"]

    def local_models():
        try:
            return list(m._discover_vision_models())
        except Exception:
            return []

    def vaplus_chat(messages, context, requested):
        if not use_venice(store, requested, local_models()):
            return orig_chat(messages, context, requested)
        turns = [{"role": t["role"], "content": str(t.get("content", ""))[:4000]}
                 for t in (messages or [])[-12:] if t.get("role") in ("user", "assistant")]
        system = "\n\n".join(x for x in (m.SYSTEM, VAPLUS_ADDENDUM, (context or "").strip()) if x)
        try:
            resp = _call(store, client_factory, lambda model: build_chat_body(model, system, turns))
        except RuntimeError as e:
            SESSION["last_error"] = str(e)
            raise
        text, cut = reply_text(resp)
        reply, actions = m._split(text)
        return (reply + LENGTH_NOTE if cut else reply), actions

    def vaplus_tour(parts, context, requested):
        if not use_venice(store, requested, local_models()):
            return orig_tour(parts, context, requested)
        system = m.TOUR_SYSTEM + "\n\n" + (context or "").strip()[:6000]
        user = "PARTS:\n" + (parts or "")[:16000] + "\n\nWrite the tour as JSON."
        try:
            # an 8000-token strict-JSON tour of a big workflow can take well over a minute
            resp = _call(store, client_factory, lambda model: build_tour_body(model, system, user, m.TOUR_SCHEMA), timeout=150)
        except RuntimeError as e:
            SESSION["last_error"] = str(e)
            raise
        text, _ = reply_text(resp)
        try:
            return json.loads(text[text.index("{"):])
        except ValueError:
            return m._salvage(text)

    def vaplus_plan(requested=None):
        plan = orig_plan(requested)
        if not use_venice(store, requested, local_models()):
            return plan
        return cloud_plan(store, plan.get("vram_gb", 0.0) if isinstance(plan, dict) else 0.0)

    for f in (vaplus_chat, vaplus_tour, vaplus_plan):
        f._vaplus = True
    m._chat, m._tour, m._plan = vaplus_chat, vaplus_tour, vaplus_plan


def ensure_patched(store, client_factory=Client, modules=None) -> str:
    """'patched' | 'already' | 'missing' (LC Vision not loaded yet) | 'changed' (LC Vision changed; left alone)."""
    with _LOCK:
        try:
            m = find_va(modules)
            if m is None:
                return "missing"
            if getattr(m._chat, "_vaplus", False):
                return "already"
            if not all(hasattr(m, n) for n in NEEDED):
                print("[VA+] Vision Assistant changed; VA+ brain disabled")
                return "changed"
            ORIGINALS.update(_chat=m._chat, _tour=m._tour, _plan=m._plan)
            _wrap(m, store, client_factory)
            return "patched"
        except Exception as e:
            print(f"[VA+] could not patch Vision Assistant: {e}")
            return "changed"
