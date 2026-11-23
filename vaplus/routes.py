"""VA+ HTTP routes (/va_plus/*) and the status rewrite for VA's /lc_vision/assistant/status. No endpoint returns the key,
installs anything or restarts ComfyUI (ComfyUI listens on the LAN without auth)."""
import asyncio
import json

from aiohttp import web

from . import patch
from .venice import Client

STATUS_PATHS = ("/lc_vision/assistant/status", "/api/lc_vision/assistant/status")
MAX_BODY = 10_000


def rewrite_status(payload: dict, venice_on: bool) -> dict:
    if venice_on and isinstance(payload, dict):
        payload["available"], payload["why"] = True, ""
    return payload


def summarize_models(data: list) -> list:
    out = []
    for m in data or []:
        spec = m.get("model_spec") or {}
        if not (spec.get("capabilities") or {}).get("supportsFunctionCalling"):
            continue
        price = spec.get("pricing") or {}
        out.append({"id": m.get("id"), "name": spec.get("name") or m.get("id"),
                    "price_in": (price.get("input") or {}).get("usd"), "price_out": (price.get("output") or {}).get("usd")})
    return out


async def _body(request):
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) and len(json.dumps(data)) <= MAX_BODY else None


async def post_key(store, request):
    data = await _body(request)
    if data is None or not isinstance(data.get("key", ""), str):
        return web.json_response({"ok": False}, status=400)
    store.set_key(data.get("key", ""))
    return web.json_response({"ok": True, "has_key": store.has_key()})


async def post_config(store, request):
    data = await _body(request)
    if data is None:
        return web.json_response({"error": "expected a JSON object"}, status=400)
    return web.json_response(store.save(data))


async def get_status(store, state):
    cfg = store.load()
    return web.json_response({"patch": state.get("patch", "missing"), "enabled": cfg["enabled"], "has_key": store.has_key(),
                              "model": cfg["model"], "cost_usd": round(patch.SESSION["cost_usd"], 4),
                              "last_error": patch.SESSION["last_error"], "status": patch.SESSION["status"],
                              "middleware": state.get("middleware", False)})


async def get_models(store):
    if not store.has_key():
        return web.json_response([])
    try:
        data = await asyncio.get_running_loop().run_in_executor(None, lambda: Client(store.get_key()).models())
    except Exception:
        return web.json_response([])
    return web.json_response(summarize_models(data))


def register(server, store, state):
    r = server.routes

    @r.post("/va_plus/key")
    async def _key(request):
        return await post_key(store, request)

    @r.post("/va_plus/config")
    async def _config(request):
        return await post_config(store, request)

    @r.get("/va_plus/status")
    async def _status(request):
        state["patch"] = patch.ensure_patched(store) if state.get("patch") in (None, "missing") else state["patch"]
        return await get_status(store, state)

    @r.get("/va_plus/models")
    async def _models(request):
        return await get_models(store)

    @web.middleware
    async def status_middleware(request, handler):
        response = await handler(request)
        if request.method != "GET" or request.path not in STATUS_PATHS or not isinstance(response, web.Response):
            return response
        if not patch.use_venice(store, request.query.get("model"), []):
            return response
        try:
            payload = json.loads(response.text)
        except Exception:
            return response
        return web.json_response(rewrite_status(payload, True), status=response.status)

    try:
        server.app.middlewares.append(status_middleware)
        state["middleware"] = True
    except Exception:  # a frozen app: skip; status reports it
        state["middleware"] = False
