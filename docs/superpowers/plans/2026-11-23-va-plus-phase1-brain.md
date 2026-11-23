# VA+ Phase 1 (Brain) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vision Assistant's chat and guided tours run on a Venice model when VA+ is on, with no VRAM use and no edits to LC Vision files.

**Architecture:** A new custom node pack `ComfyUI_VA_Plus` finds the already-loaded `lc_vision_assistant` module through `sys.modules` and swaps only `_chat`, `_tour` and `_plan` for wrappers. Each wrapper routes to Venice or calls the original. Settings and the key live in VA+'s own files, and page code mirrors settings and shows a status line.

**Tech Stack:** Python 3.13 (ComfyUI venv; stdlib `urllib.request`, `json`, `threading`; aiohttp only through ComfyUI's `server.PromptServer`), plain ES-module JS for the ComfyUI frontend, pytest for tests. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-23-va-plus-design.md` (sections 5.1, 5.2, 5.6, 5.7, 6, 7, 8 for Phase 1)

## Global Constraints

- Pack folder `ComfyUI/custom_nodes/ComfyUI_VA_Plus`; Python package inside it: `vaplus/`; routes prefixed `/va_plus/`; settings ids `VAPlus.*`, category `["LC Settings ⚙️", "Vision Plus"]`.
- Never `import` LC Vision files by name and never register `/lc_vision/*` routes. Patch only `m._chat`, `m._tour`, `m._plan`.
- Venice base `https://api.venice.ai/api/v1`; default model `deepseek-v4-1-flash-1017-uncensored`; fallback `venice-uncensored-1-2`.
- Every Venice body has `venice_parameters: {"include_venice_system_prompt": false, "enable_web_search": "off"}`, `reasoning_effort: "low"`, `temperature: 0.3`, chat `max_completion_tokens: 4000`. Never send `repeat_penalty` or `top_k`.
- Timeouts: 10 s connect, 60 s per call. No retry on 4xx; one retry on 5xx or timeout.
- Key: write-only, in `ComfyUI/user/default/va_plus/secrets.json`, `VENICE_API_KEY` env fallback, never returned, logged or put in a URL.
- Config: `ComfyUI/user/default/va_plus/config.json` with `{"enabled": true, "model": "<id>", "web_search": true, "show_cost": true}`.
- No new pip dependencies. Tests run with `..\..\.venv\Scripts\python.exe -m pytest tests -q` from the pack folder.

## Review Focus

1. **LC Vision missing or changed** (renamed `_chat` etc.): VA+ must not crash ComfyUI; the patch is skipped and status says why. → Task 3 `test_fail_closed_when_names_missing`.
2. **No key set, or key rejected (401):** VA must keep working locally when there's no key; with a bad key the user sees "Your Venice key was rejected…", not a traceback. → Task 2 `test_error_messages`, Task 3 `test_routes_local_without_key`.
3. **User picks a local model or "off" in LC Settings:** that choice wins over VA+. → Task 3 `test_local_choice_wins`, `test_off_wins`.
4. **Reply wrapped in `<think>` or cut off (`finish_reason == "length"`):** thinking is stripped and the "cut off" note is added like VA does. → Task 2 `test_strip_and_length_note`.
5. **Tour JSON truncated mid-way:** falls back to `m._salvage` instead of erroring. → Task 3 `test_tour_salvage_fallback`.

---

### Task 1: Pack skeleton, config and key store

**Files:**
- Create: `__init__.py`, `vaplus/__init__.py`, `vaplus/config.py`, `tests/conftest.py`, `tests/test_config.py`, `LICENSE`, `.gitignore`, `pyproject.toml`

**Interfaces:**
- Produces: `vaplus.config.Store(root: pathlib.Path)` with `.load() -> dict` (defaults merged), `.save(update: dict) -> dict` (validates keys and types, ignores unknown), `.set_key(key: str) -> None`, `.get_key() -> str | None` (file, then env `VENICE_API_KEY`), `.has_key() -> bool`. `DEFAULTS = {"enabled": True, "model": "deepseek-v4-1-flash-1017-uncensored", "web_search": True, "show_cost": True}`. `vaplus.config.default_root() -> Path` = `folder_paths.get_user_directory()/default/va_plus`.

- [ ] **Step 1: Write failing tests** in `tests/test_config.py` (use `tmp_path`):
  - `test_defaults`: `Store(tmp_path).load() == DEFAULTS`
  - `test_save_validates`: `save({"enabled": "yes", "model": 5, "junk": 1})` leaves `enabled` True and `model` the default, and has no `junk`
  - `test_key_roundtrip_and_env`: `set_key("abc")` → `get_key() == "abc"`; with no file and `monkeypatch.setenv("VENICE_API_KEY","env")` → `"env"`
  - `test_key_not_in_config`: after `set_key`, `"abc"` is not in `config.json` text

  `conftest.py` puts the pack folder on `sys.path`.
- [ ] **Step 2: Run** `..\..\.venv\Scripts\python.exe -m pytest tests/test_config.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `vaplus/config.py`. Writes are atomic (tmp file + `os.replace`); `secrets.json` = `{"venice_api_key": "..."}`. Root `__init__.py`: `WEB_DIRECTORY = "./web"`, `NODE_CLASS_MAPPINGS = {}`, `NODE_DISPLAY_NAME_MAPPINGS = {}`; later tasks wire routes and patching. `.gitignore` ignores `__pycache__/`. `LICENSE` is MIT (2026, VA+ authors) with a line crediting LC Vision by lonecatone23 (MIT).
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit:** `git init` (first task only), `git add -A`, `git commit -m "Add VA+ skeleton, config and key store"`.

### Task 2: Venice client

**Files:**
- Create: `vaplus/venice.py`, `tests/test_venice.py`

**Interfaces:**
- Consumes: nothing (pure; HTTP via an injectable `opener`).
- Produces:
  - `VeniceError(RuntimeError)` with a plain-language `str()`
  - `build_chat_body(model: str, system: str, turns: list[dict], max_tokens: int = 4000) -> dict`
  - `build_tour_body(model: str, system: str, user: str, schema: dict) -> dict`
  - `strictify(schema: dict) -> dict` (deep copy; every object gets `additionalProperties: False` and `required` = all its properties)
  - `class Client(key: str, opener=urllib.request.urlopen)` with `.chat(body: dict) -> dict` (parsed JSON, adds `"_cost_usd": float|None` from `usage`/`cost` or header `x-venice-balance-usd` ignored) and `.models() -> list[dict]` (GET `/models?type=text`, cached 15 min)
  - `reply_text(resp: dict) -> tuple[str, bool]`: (content with `<think>…</think>` stripped, `finish_reason == "length"`)

- [ ] **Step 1: Write failing tests:**
  - `test_chat_body_shape`: has `venice_parameters` exactly as in Global Constraints, `reasoning_effort=="low"`, `temperature==0.3`, `max_completion_tokens==4000`, first message `role=="system"`, no `repeat_penalty`/`top_k`
  - `test_tour_body_uses_strict_schema`: `response_format == {"type":"json_schema","json_schema":{"name":"tour","strict":True,"schema":strictify(s)}}`
  - `test_strictify_nested`: nested `steps.items.settings.items` objects all get `additionalProperties False` and full `required`
  - `test_error_messages`: a fake opener raising HTTPError maps 401→"Your Venice key was rejected. Set it again in Settings > Vision Plus.", 402→"Your Venice balance is empty.", 429→"Venice is rate-limiting you. Wait a minute.", 500 twice→"Venice didn't answer. Try again."
  - `test_no_retry_on_4xx`: 400 calls the opener once; 503 then 200 calls it twice and returns
  - `test_key_only_in_header`: the captured request has `Authorization: Bearer k` and `k` is not in the URL
  - `test_strip_and_length_note`: `reply_text` strips the think block and reports length
- [ ] **Step 2: Run** `... -m pytest tests/test_venice.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `vaplus/venice.py` with `urllib.request.Request` (JSON body, `timeout=60`). Map `URLError`/`TimeoutError` like 5xx. Never log the key.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `"Add Venice client with strict schema, error mapping and retries"`.

### Task 3: Find and patch Vision Assistant

**Files:**
- Create: `vaplus/patch.py`, `tests/test_patch.py`, `tests/fake_va.py` (a module object exposing `SYSTEM`, `TOUR_SYSTEM`, `TOUR_SCHEMA`, `_chat`, `_tour`, `_plan`, `_split`, `_salvage`, `strip_thinking`, `_discover_vision_models`, mimicking VA's signatures)

**Interfaces:**
- Consumes: `Store` (Task 1), `Client`, `build_*`, `reply_text`, `VeniceError` (Task 2).
- Produces:
  - `find_va(modules: dict = sys.modules, mappings: dict | None = None) -> ModuleType | None`: first via `mappings["LCVisionLoader"].__module__` package + `.lc_vision_assistant`, else scan for keys ending `.lc_vision_assistant` that have `SYSTEM`, `_chat`, `_tour`
  - `ensure_patched(store: Store, client_factory=Client) -> str`: returns `"patched" | "already" | "missing" | "changed"`, idempotent; stores originals in `ORIGINALS`
  - `use_venice(store, requested, local_models) -> bool`: True iff enabled, key present, `requested != "off"`, `requested not in local_models`
  - `cloud_plan(store, vram_gb: float) -> dict`: `{"name": "Venice · " + model, "path": None, "ctx": 131072, "need_gb": 0.0, "vram_gb": vram_gb, "tours": True, "lite": False, "mode": "cloud", "why": ""}`
  - `SESSION = {"cost_usd": 0.0, "last_error": "", "status": ""}`
  - `VAPLUS_ADDENDUM: str`. Phase 1 text: one short paragraph saying answers come from VA+ on Venice and the VA rules above still apply. Later phases append the action grammar.

- [ ] **Step 1: Write failing tests:**
  - `test_find_via_mappings` and `test_find_via_scan`
  - `test_fail_closed_when_names_missing`: fake without `_tour` → `"changed"`, nothing replaced
  - `test_idempotent`: second call → `"already"`, the wrapper isn't wrapped twice
  - `test_routes_local_without_key`: no key → the original `_chat` is called
  - `test_local_choice_wins`: `requested` in `_discover_vision_models()` → original
  - `test_off_wins`: `requested=="off"` → original `_plan`
  - `test_chat_via_venice`: the fake client returns content with a fenced actions block; the wrapper returns `m._split(...)` output; the system prompt sent starts with `m.SYSTEM` and contains `VAPLUS_ADDENDUM` and the context; the length note matches VA's text `"\n\n*(That ran long and got cut off. Say \"continue\" for the rest.)*"`
  - `test_tour_salvage_fallback`: truncated JSON → `m._salvage` result returned
  - `test_plan_cloud`: the patched `_plan(None)` with Venice on equals `cloud_plan`
- [ ] **Step 2: Run** `... -m pytest tests/test_patch.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `vaplus/patch.py`. Wrappers keep VA's signatures `(messages, context, requested)`, `(parts, context, requested)`, `(requested=None)`. Chat turns: last 12, user/assistant only, content capped at 4000 chars (VA's rule). Tour user text: `"PARTS:\n" + parts[:16000] + "\n\nWrite the tour as JSON."`, summary ≤ 6000 chars. On a 404 model error, retry once with the fallback model and set `SESSION["status"]`. Add `cost_usd` to `SESSION`. A `VeniceError` propagates as `RuntimeError` (VA shows it as an error bubble). If `ensure_patched` raises internally, log one line `[VA+] ...` and return `"changed"`.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `"Patch Vision Assistant chat, tour and plan to route through Venice"`.

### Task 4: Routes, status middleware and startup wiring

**Files:**
- Create: `vaplus/routes.py`, `tests/test_routes.py`
- Modify: `__init__.py`

**Interfaces:**
- Consumes: `Store`, `ensure_patched`, `SESSION`, `Client.models`.
- Produces HTTP:
  - `POST /va_plus/key {key}` → `{ok, has_key}` (empty string deletes the key)
  - `POST /va_plus/config {...}` → saved config
  - `GET /va_plus/status` → `{patch: str, enabled, has_key, model, cost_usd, last_error, status}`
  - `GET /va_plus/models` → `[{"id", "name", "price_in", "price_out"}]` (text models with `supportsFunctionCalling`; `[]` without a key or on error)
  - Status middleware for GET `/lc_vision/assistant/status` and `/api/lc_vision/assistant/status`: when `use_venice(store, requested=request.query.get("model"), local_models=[])` is true, set `available: true` and `why: ""` in the JSON
  - Function `rewrite_status(payload: dict, venice_on: bool) -> dict`, pure, for tests
- Startup: `__init__.py` calls `ensure_patched` at import inside try/except, appends `on_startup` to call it again, registers routes and the middleware, and prints one line `[VA+] Vision Assistant: <result>`.

- [ ] **Step 1: Write failing tests:**
  - `test_rewrite_status_on` / `_off` (pure function)
  - `test_key_endpoint_never_returns_key`: call the handler with a stub request; the response text doesn't contain the key
- [ ] **Step 2: Run** `... -m pytest tests/test_routes.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `vaplus/routes.py`. Handlers are thin and call `Store`/`patch`. The middleware is an `@web.middleware` appended to `PromptServer.instance.app.middlewares` only if the app isn't frozen; otherwise skip it and note it in status. Validate JSON bodies (dict only, size ≤ 10 KB).
- [ ] **Step 4: Run all tests:** `... -m pytest tests -q`. Expected: all PASS.
- [ ] **Step 5: Manual check:** restart ComfyUI. The log has `[VA+] Vision Assistant: patched`; `GET http://127.0.0.1:8188/va_plus/status` returns `"patch": "patched"`.
- [ ] **Step 6: Commit** `"Add VA+ routes, status middleware and startup patching"`.

### Task 5: Page code: settings, key dialog, status line

**Files:**
- Create: `web/va_plus.js` (the only top-level JS file; helpers inside it, because every `.js` under `web/` auto-loads)

**Interfaces:**
- Consumes: the Task 4 routes; ComfyUI `app.registerExtension`, `app.extensionManager.setting`, `api.fetchApi`.
- Produces:
  - Settings `VAPlus.Enabled` (boolean, true), `VAPlus.Model` (combo from `/va_plus/models`, default the spec default), `VAPlus.WebSearch` (boolean, true), `VAPlus.ShowCost` (boolean, true), `VAPlus.Key` (a button-type setting opening a password prompt that POSTs to `/va_plus/key` and never stores the value in settings)
  - Each change POSTs to `/va_plus/config`
  - Status line: when an element `.va` exists, a `div.vaplus-status` is inserted after it (MutationObserver), text from `/va_plus/status` refreshed every 30 s and after each chat: `VA+ · Venice · <model> · $<cost> this session`, or `VA+ off: key missing` / `VA+ off: Vision Assistant changed`

- [ ] **Step 1: Implement** `web/va_plus.js` as above. No side effects beyond `registerExtension`; never put the key in `localStorage` or settings.
- [ ] **Step 2: Manual check:** reload the page.
  - Settings › LC Settings ⚙️ › Vision Plus shows the 5 entries.
  - Set the key → the status line shows the model.
  - Ask VA "where is the sampler?" → the answer comes from Venice (cost goes up, no VRAM rise in `nvidia-smi`) and the node glows.
  - Build a guided tour → it completes and saves.
  - In LC Settings pick a local model → the answer is local again.
  - Set `VAPlus.Enabled` off → VA behaves as before.
- [ ] **Step 3: Commit** `"Add VA+ settings, key dialog and status line"`.

### Task 6: Phase 1 docs and push

**Files:**
- Create: `README.md`, `CHANGELOG.md`, `docs/architecture.md` (short; links to the spec and describes what Phase 1 implements), `docs/privacy-and-cost.md` (spec section 6 verbatim facts), `docs/troubleshooting.md` (key errors, 409 busy, "Vision Assistant changed", local-model choice wins, how to switch off)

- [ ] **Step 1: Write the docs.** The README covers what VA+ is, requirements (LC Vision installed, Venice key), install (git clone into custom_nodes, restart), set key, use, switching back to local, uninstall (delete folder; VA is unaffected), credits.
- [ ] **Step 2: Check:** every setting id and route named in the docs exists in the code (`rg "VAPlus\.|/va_plus/"`).
- [ ] **Step 3: Commit** `"Add Phase 1 documentation"`.
- [ ] **Step 4: Push and mirror.** After the user has chosen the GitHub route and visibility: add the remote and `git push -u origin main`. Create the Notion page (private draft unless told otherwise) mirroring the README, architecture and links.

---

**Later plans** (one each, written when the previous phase ships): Phase 2 Knowledge (spec 5.3), Phase 3 Building (5.4), Phase 4 Installing (5.4 install row), Phase 5 Polish (5.5, opt-in LC Note translate).
