# Architecture

The full design is in [specs/2026-11-23-va-plus-design.md](superpowers/specs/2026-11-23-va-plus-design.md). This page covers what is built so far: **Phase 1 (Brain)**.

## How VA+ plugs into Vision Assistant

1. **Find, never import.** VA+ finds LC Vision's already-loaded `lc_vision_assistant` module.
   - It starts from `nodes.NODE_CLASS_MAPPINGS["LCVisionLoader"]`'s package name.
   - Fallback: it scans `sys.modules` for a key ending in `.lc_vision_assistant`.
   - Importing LC files by name would load a second copy with duplicate routes, so VA+ never does it.
2. **When.** `ensure_patched()` runs at VA+ import, again on ComfyUI's `on_startup` (every pack is loaded by then), and on the first `/va_plus/status` call. Running it again is harmless.
3. **What is replaced.** Only `m._chat`, `m._tour` and `m._plan`. VA's routes look these up at call time.
   - Shared helpers (`_plan_for`, `_free`, `_llama_kwargs`, `_make_room`, `_discover_vision_models`) are untouched. LC Note's translator uses them, so they stay local.
4. **Routing.** Each wrapper uses Venice when all of these are true; otherwise it calls VA's original function unchanged:
   - VA+ is enabled
   - a key is set
   - LC's chat model isn't `off`
   - the requested model isn't a local model name
5. **Fail closed.** If LC Vision changes the names VA+ needs, VA+ leaves everything alone and the status line says "VA+ off: Vision Assistant changed".

## Venice calls (`vaplus/venice.py`)

- **Every request** sends `venice_parameters {include_venice_system_prompt:false, enable_web_search:"off"}`, `reasoning_effort:"low"` and `temperature:0.3`, plus:
  - Chat: `max_completion_tokens 4000`
  - Tours: strict `json_schema` (VA's tour schema closed with `additionalProperties:false`, every field required), `max_completion_tokens 8000`
- **Errors and retries:**
  - 4xx is never retried, because Venice locks keys after many failed 4xx.
  - 5xx and timeouts get one retry.
  - 404 (model gone) falls back to `venice-uncensored-1-2`.
- **Chat prompt.** `system` = VA's own `SYSTEM` + a short VA+ note + VA's workflow context. Then the last 12 user and assistant turns, each cut to 4000 characters (VA's own rules). Replies go through VA's `_split`, so action blocks keep working.
- **Tours.** These go through VA's `TOUR_SYSTEM`. A cut-off reply falls back to VA's `_salvage`. Tours save in Lonecat's format, so LC Optimizer and other users can read them.

## Status

- `_plan` returns a "cloud" plan: tours on, 0 GB, `mode: "cloud"`.
- A middleware on `GET /lc_vision/assistant/status` (and `/api/...`) sets `available: true` when Venice will answer. That covers PCs without llama-cpp or a local model.

## Files

| Path | Purpose |
|---|---|
| `__init__.py` | Registers routes and the middleware, patches at import and on startup. Never raises. |
| `vaplus/config.py` | `config.json` and the write-only `secrets.json` in `ComfyUI/user/default/va_plus/`, with `VENICE_API_KEY` env fallback |
| `vaplus/venice.py` | Venice client and request builders |
| `vaplus/patch.py` | Finding and patching VA, routing rule, session cost |
| `vaplus/routes.py` | `/va_plus/key`, `/va_plus/config`, `/va_plus/status`, `/va_plus/models`, status middleware |
| `web/va_plus.js` | Settings, key command, status line |
| `tests/` | pytest suite (`..\..\.venv\Scripts\python.exe -m pytest tests -q`) |

## HTTP routes

| Route | Body / result |
|---|---|
| `POST /va_plus/key` | `{key}` → `{ok, has_key}`. An empty key removes it. The key is never returned. |
| `POST /va_plus/config` | `{enabled, model, web_search, show_cost}` → saved config (unknown or invalid fields ignored) |
| `GET /va_plus/status` | `{patch, enabled, has_key, model, cost_usd, last_error, status, middleware}` |
| `GET /va_plus/models` | Venice text models with function calling: `[{id, name, price_in, price_out}]` |

No VA+ route installs packs, restarts ComfyUI or returns secrets. ComfyUI listens on your LAN without auth.
