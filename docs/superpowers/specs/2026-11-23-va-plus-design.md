# VA+ (Vision Assistant Plus): design

- **Date:** 2026-11-23
- **Status:** draft, awaiting approval
- **Pack folder:** `ComfyUI/custom_nodes/ComfyUI_VA_Plus` (git repo; pushed to GitHub once approved)
- **Extends:** Vision Assistant (VA) in LC Vision by Lonecat (`ComfyUI_LC_Vision_nodes`, MIT). VA+ never copies LC code; it calls into it and adds a 1-line hook.

---

## 1. Intent

The user builds a lot of NSFW art in ComfyUI on an RTX 3080 (10 GB). Vision Assistant is the assistant they trust most. It points at the canvas: nodes glow, the view zooms to them, it offers one-click fixes, checkups, snapshots and guided tours. Two things hold it back for this user:

1. **The brain is a local Qwen3-VL in VRAM.** On a 10 GB card it gets about 5 GB, which is a small model with a short context, so it can't build guided tours (those need a 20 GB+ card).
2. **It can fix a workflow but can't help build one.** The user's biggest pain has been discovery and assembly: finding the right Krea 2 nodes for image-to-image edit among five similar Krea packs, and wiring a two-LoRA (regional) setup.

VA+ keeps everything VA does and adds:

- **A Venice.ai brain.** An uncensored cloud model replaces the local one. It uses no VRAM, unlocks tours, and doesn't refuse adult work.
- **Recommendations.** It knows the user's installed nodes, their packs' READMEs and example workflows, the ComfyUI-Manager pack list and, for brand-new packs, the web. It prefers Lonecat's LC nodes when one fits.
- **Building on the canvas.** It adds and wires nodes, loads a pack's known-good example and carries the user's models, LoRAs and prompts over, and installs packs through the Manager. Every change is shown first, needs a yes, and can be undone.

**Success looks like:** the user asks "set up Krea 2 image-to-image edit" or "add a second character LoRA without them bleeding". VA+ names the right pack and nodes with reasons, highlights where they go, and builds it after a yes. The result runs, and one Undo removes it.

## 2. Goals, non-goals, anti-goals

**Goals**
- G1. VA chat and guided tours answered by a Venice model when VA+ is on, with no VRAM use.
- G2. Node, pack and example-workflow recommendations grounded in what's installed (first), the Manager list (second) and web search (last).
- G3. New canvas actions: add node, connect, load example workflow (new tab, carry-over), install pack (Manager, explicit yes), open link.
- G4. One-step undo for every VA+ structural change.
- G5. VA, LC123, LC Note, LC Optimizer, tours, snapshots and swaps keep working exactly as today, with VA+ on, off or uninstalled.
- G6. Documented to the letter: README, architecture, hook, actions, knowledge, privacy and cost, troubleshooting, changelog, plus a Notion mirror.

**Non-goals (v1)**
- Replacing VA's checkup, swaps, tours UI or snapshots. VA+ builds on them.
- Copilot-style community workflow library or "generate a workflow from nothing". VA+ assembles from installed packs and their examples.
- Image or vision input to the brain (VA's chat is text-only). Later option: a Venice vision model.
- Powering LC Vision's other local-model features (LC Note translate and spelling, Caption, Prompt Enhancer nodes) with Venice. Listed as a later, opt-in phase.
- Removing ComfyUI-Copilot. That's a separate decision once VA+ works.

**Anti-goals (a failure even if it "works")**
- A1. Anything that changes VA's behaviour when VA+ is off or uninstalled.
- A2. Any canvas change without the user seeing it first and saying yes (except glow, zoom and open-link, which are already "safe" in VA).
- A3. The Venice key reaching the browser, a log line, a URL or any server except Venice.
- A4. Data sent anywhere except Venice (chat and search) and, only after a yes, the Manager install path (comfy.org and GitHub).
- A5. Adding a content filter or refusals on top of the uncensored model.
- A6. Importing LC Vision's Python files a second time (duplicate routes and state), or registering any `/lc_vision/*` route.
- A7. Downgrading shared Python packages (ComfyUI needs SQLAlchemy 2.x and so on). VA+ adds no new dependencies.

## 3. Constraints

- **Environment:** Windows 11, Comfy Desktop, Python 3.13 uv-managed venv, ComfyUI frontend 1.5x, ComfyUI-Manager 4.2.2 (v2 API), RTX 3080 10 GB. ComfyUI listens on `0.0.0.0`, so endpoints are reachable from the LAN without auth.
- **Load order:** custom-node folders load in `os.listdir` order. `ComfyUI_VA_Plus` sorts after `ComfyUI_LC_Vision_nodes`, but VA+ must not rely on that (see 5.1).
- **VA's backend** holds one `_LOCK` per request; a second request waits 15 s, then gets 409. The page has no timeout. VA+ calls need firm timeouts (total ≤ 90 s).
- **VA's page** strips URLs it didn't provide, caps actions at 12 (`_split`), runs vetted actions in order in `carryOut` with no try/catch, and one "Yes" approves every non-safe action in a message.
- **VA's undo** (`va_core.capture/restore`) restores only widget values and modes, not added nodes or links.
- **Venice:** OpenAI-compatible at `https://api.venice.ai/api/v1`.
  - `include_venice_system_prompt` defaults to true; VA+ turns it off.
  - `deepseek-v4-1-flash-1017-uncensored` defaults to high reasoning effort, and reasoning tokens count against the reply budget.
  - Strict `json_schema` needs `additionalProperties:false` and every property required.
  - More than 50 failed 4xx in 30 s locks the key into 429.
  - Web-search augment costs about $0.01 a call.
  - Model ids rotate, so the model must be configurable with a fallback.
- **Cost (live catalog, 2026-11-23):**
  - `deepseek-v4-1-flash-1017-uncensored`: $0.33 / $1.32 per M tokens (in / out).
  - `venice-uncensored-1-2`: $0.20 / $0.90 per M tokens.
- **License:** VA+ is MIT. It credits LC Vision (MIT, lonecatone23) and copies none of its code.

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| 1 | **Own pack + 1-line hook in VA** | All new code in `ComfyUI_VA_Plus`. The backend is monkeypatched at runtime, and the page needs one line in `va_chat.js` `vet()`. An LC Vision update can only remove the hook; VA+ re-applies it at startup. Lonecat's updates keep flowing, and the LC links (LC Note reader, tour format, swap rules) stay intact. | **Chosen** by the user |
| 2 | Fork VA into our pack | Immune to updates, but freezes Lonecat's swap rules and checkup, and leaves duplicate checkups or two readers. LC Note keeps using the original. | Rejected |
| 3 | Edit LC Vision files directly | Quickest, but every LC Vision update wipes all of it. | Rejected |

## 5. Design

### 5.0 Overview

```
 ┌──────────── Browser (ComfyUI page) ────────────┐        ┌──────── ComfyUI server (Python) ─────────┐
 │ VA page code (Lonecat, untouched except hook)  │        │ LC Vision: lc_vision_assistant (untouched)│
 │   vet() default ──► globalThis.VAPlus.vet(a)    │  chat  │   /lc_vision/assistant/chat ─► m._chat ───┼──► VA+ brain ─► Venice API
 │   carryOut() runs VA+ run() in order            │ ─────► │   /lc_vision/assistant/tour ─► m._tour ───┤        ▲   (tool loop)
 │ VA+ page code (ours)                            │        │   /lc_vision/assistant/status ─► m._plan ─┤        │
 │   vet/run for vaplus_* actions, undo, toasts,   │        │ VA+ (ours)                                │        │
 │   settings, Manager install + restart prompts   │ ─────► │   /va_plus/* routes, config, key store    │   knowledge index
 └─────────────────────────────────────────────────┘        │   knowledge index (BM25)  ────────────────┼──► (nodes, READMEs,
                                                             └───────────────────────────────────────────┘     examples, Manager caches)
```

### 5.1 Finding and patching VA (backend)

- **Find, never import.** Look up `nodes.NODE_CLASS_MAPPINGS['LCVisionLoader']` → its `__module__` package → `sys.modules[pkg + '.lc_vision_assistant']`. Fallback: scan `sys.modules` for keys ending in `.lc_vision_assistant` whose module has `SYSTEM`, `_chat` and `_tour`. Never `import` LC files by name (that creates a second copy with duplicate routes).
- **When:** `ensure_patched()` runs at VA+ import, again on `PromptServer.instance.app.on_startup` (after all packs load, before the first request), and lazily on the first `/va_plus/*` call. It's idempotent.
- **What is patched:** only `m._chat`, `m._tour` and `m._plan` (the routes look them up as module globals at call time). **Never** `_plan_for`, `_free`, `_llama_kwargs`, `_make_room` or `_discover_vision_models`; LC Note translate, spelling and write-note import those and must stay local.
- **Fail closed:** if the expected names or signatures are missing (an LC update changed them), skip patching, log one line (`[VA+] Vision Assistant changed; VA+ brain disabled`) and report it in `/va_plus/status`.
- **Routing rule** (in each wrapper): use Venice when VA+ is enabled, a key is present, `LCVision.Chat.Model` isn't `"off"`, and the requested model isn't a local model name. Otherwise call the original function unchanged. Choosing a local model in LC Settings always means local, so the user can switch back without disabling VA+.

### 5.2 Brain (Venice)

- **Chat request:**
  - `system` = `m.SYSTEM` + **VA+ addendum** + VA's context (workflow summary, notes, checkup) + **knowledge block**, then the last 12 turns from VA.
  - `model` = the VA+ setting (default `deepseek-v4-1-flash-1017-uncensored`; on a 404 or deprecation, fall back to `venice-uncensored-1-2` and say so).
  - `venice_parameters: {include_venice_system_prompt:false, enable_web_search:"off"}`. Web search goes through the tool, so it's capped.
  - `reasoning_effort:"low"`, `max_completion_tokens ≈ 4000`, `temperature 0.3`. No llama-only fields (`repeat_penalty`, the `json_object`+schema form).
- **VA+ addendum to SYSTEM:** relaxes two VA rules for VA+ actions only:
  - "never invent a node id": new nodes use `ref` names.
  - "only give links from the workflow": links go through `vaplus_open`.

  It also documents the `vaplus_*` action grammar (5.4), sets "prefer installed, then LC twins, then Manager packs, then web", and limits install proposals to their own message.
- **Reply parsing:** reuse `m._split` and `m.strip_thinking`. VA+ raises the 12-action cap for its own replies by post-processing: if a build plan needs more than 12 actions, the backend packs them into one `vaplus_batch` action (5.4).
- **Install isolation (backend-enforced):** if a reply contains `vaplus_install_pack` alongside other non-safe actions, the backend drops the others and appends "I'll do the rest after the install."
- **Tours:** wrap `m._tour`. Send `m.TOUR_SYSTEM` + summary, and `response_format {type:"json_schema", json_schema:{name:"tour", strict:true, schema: strictify(m.TOUR_SCHEMA)}}`, where strictify adds `additionalProperties:false` and requires every property. Stream internally to avoid gateway timeouts, and on a cut-off reply fall back to `m._salvage`. Tours save in Lonecat's format (`graph.extra.vision_assistant.tour`), so LC Optimizer keeps reading author picks and tours play for anyone with LC Vision.
- **Status:** wrap `m._plan`. When Venice would answer, return `{name:"Venice · <model>", path:null, ctx:131072, need_gb:0, vram_gb:<real>, tours:true, lite:false, mode:"cloud", why:""}`. Also add an aiohttp middleware on `GET /lc_vision/assistant/status` and `/api/lc_vision/assistant/status` that sets `available:true` when Venice is configured. That covers PCs without llama-cpp or a GGUF, and runs only while VA+ is enabled. VA's own labels ("~GB", "k ctx", the VRAM tooltip) may read oddly with a cloud plan; VA+ shows its own status line (5.7) and documents this.
- **Errors → plain messages** (raised as `RuntimeError`, shown by VA as an error bubble):

| Venice error | Message shown |
|---|---|
| 401 | "Your Venice key was rejected. Set it again in Settings > Vision Plus." |
| 402 | "Your Venice balance is empty." |
| 429 | "Venice is rate-limiting you. Wait a minute." |
| 5xx / timeout | "Venice didn't answer. Try again." |

  4xx responses are never auto-retried (to avoid the 50-failure lockout); 5xx and timeouts get one retry.
- **Timeouts:** 10 s connect, 60 s per call, 90 s per whole answer including tool rounds.
- **Cost:** read `usage` and cost from each response and the `x-venice-balance-usd` header. Keep a running session total, shown in the VA+ status line.

### 5.3 Knowledge and the tool loop

**Index (server-side, pure-Python Okapi BM25, no new deps).** Built lazily on first use after startup, rebuilt when the node count or pack folder mtimes change. Sources:

| Source | Where it comes from |
|---|---|
| **Installed nodes** | `nodes.NODE_CLASS_MAPPINGS`, V1 and V3 schemas. Per node: class, display name, category, description, inputs and outputs (both combo encodings), pack folder (from `python_module`). Built inside `folder_paths.cache_helper`, with try/except per node. |
| **JS-only nodes** (LC Bypasser, LC Mute, LCNote and others, missing from Python mappings) | The page sends `LiteGraph.registered_node_types` names and titles once per session to `POST /va_plus/frontend_nodes`. |
| **READMEs and docs** | `custom_nodes/*/README*`, `docs/*.md`, `web|js/docs/<Node>.md`, chunked at headings and tagged with pack folder. |
| **Example workflows** | UI-format JSON under `example_workflows/`, `workflows/`, `examples/`, `docs/` in each pack (about 375 files). Indexed by node types used (including inside subgraph `definitions`; UUID types excluded), title and pack. Served for loading via ComfyUI's `/api/workflow_templates` when the pack exposes them, otherwise via `GET /va_plus/example`. |
| **Manager caches** | `user/__manager/cache/*custom-node-list.json` (about 6,000 packs), `*extension-node-map.json` (node type → repo), registry `*nodes.json`, `*github-stats.json`. Picked by filename suffix and newest mtime (prefixes are channel hashes). |
| **LC twins** | The page dynamically imports VA's `va_replacements.js` and `va_swap.js` by the same relative URL LC Note uses (`../ComfyUI_LC_Vision_nodes/vision_assistant/...`, no query string, so there's one module instance), builds a third-party → LC twin map, and posts it once to `/va_plus/frontend_nodes`. |

**Tokenizer:** lowercase, split camelCase, digits and underscores, keep whole class names, plus a small synonym table (i2i / img2img / image-to-image → edit / reference; krea2 / krea 2 / krea-2; lora / loras; regional / region / mask; upscale / upscaler / sr).

**Tool loop (Venice function calling, bounded):**

| Tool | Returns |
|---|---|
| `search_nodes(query, k)` | installed and JS nodes: class, title, pack, short I/O |
| `get_node_info(class)` | full inputs (names, types, combo options trimmed to 30), outputs |
| `find_examples(query, k)` | example workflow files: pack, file, node types, models referenced |
| `read_readme(pack, query)` | top README chunks for that pack |
| `search_packs(query, k)` | Manager list hits: id, title, repo, description, installed? |
| `web_search_packs(query)` | Venice `/augment/search` (github and registry hits). **At most 2 per answer**, only when local and Manager results are empty or the user asks. Toggle in settings. |

- At most 4 tool rounds. Parallel calls are allowed. Assistant messages are round-tripped unmodified (keep `reasoning_content`). The final answer must be VA-style text plus one fenced actions block.
- Simple questions ("where is the sampler") skip tools: the first call has `tool_choice:"auto"`, and the model answers directly when the workflow context is enough.
- **Privacy rule for knowledge:** send only search hits and the node info asked for. Never send the full list of the user's model filenames; for carry-over, send only the files relevant to the nodes involved.

### 5.4 Actions (page) and the hook

**Hook** (the only edit to LC Vision). In `web/vision_assistant/va_chat.js`, `vet()`'s `default:` branch becomes:

```js
      return globalThis.VAPlus?.vet?.(a) ?? { ok: false, text: `unknown action "${a.do}"` }; // VA+ hook
```

- With VA+ absent or disabled, `globalThis.VAPlus` is undefined, so the behaviour is byte-for-byte what it is today.
- **Hook installer (backend, every startup):** if the marker `// VA+ hook` is present, do nothing. Otherwise find the exact original default-branch text (CRLF-aware) and replace it, after writing `va_chat.js.vaplus-backup`. If the text doesn't match, because Lonecat changed it, don't touch the file. Mark build actions unavailable in `/va_plus/status` and tell the user in the VA+ status line.
- An LC Vision update removes the hook until the next ComfyUI start. That's documented, and VA+ shows "restart to re-enable building".

**`VAPlus.vet(a)` contract:** set when the VA+ module first runs (VA's and VA+'s extensions load in parallel with no order). It's synchronous and never throws (everything in try/catch). It returns `undefined` for any `do` it doesn't own, and returns VA's vetted shape `{ok, text, run, safe?, auto?, last?}`. `run` may be async but catches its own errors, shows a VA+ toast, and never rejects (VA's `carryOut` has no try/catch).

**Actions** (all namespaced `vaplus_*`):

| Action | Fields | Vet checks | Run |
|---|---|---|---|
| `vaplus_add_node` | `type, ref, near?` (node id or ref), `pos?`, `widgets?` (name→value), `title?` | type registered (`LiteGraph.registered_node_types`); widget names exist; combo values match options (V1/V3); ref unique in batch | create via `LiteGraph.createNode`, place near the target without overlapping, set widgets, record ref→id |
| `vaplus_connect` | `from` (id/ref), `output` (name/index), `to` (id/ref), `input` (name) | both ends resolve (refs from earlier actions in the batch count); slot exists; types compatible (`LiteGraph.isValidConnection`); dynamic-input packs allowed | `node.connect(...)`; replaces an existing input link |
| `vaplus_batch` | `title, steps:[...]` (the actions above) | every step vets; text = title + step count | runs steps in order inside one undo unit |
| `vaplus_load_example` | `pack, file, carry:{models, loras, prompts, size, seed…}` | file exists in index; lists missing nodes and models | **new workflow tab** (never replaces the current graph). Started with `setTimeout` inside `run()` so VA files its undo under the old tab. Then applies carry-over via the server helper (positional `widgets_values`, `control_after_generate` aware, skips JSON-string widgets it can't map safely and lists them) |
| `vaplus_install_pack` | `id` or `repo`, `reason` | resolvable to registry id + version, or a Manager-list entry; otherwise "manual install only" with an open-link | page calls the Manager directly: `POST /v2/manager/queue/task {kind:"install", ui_id, client_id, params:{id, version, selected_version, channel:"default", mode:"cache"}}` then `POST /v2/manager/queue/start`, tracks `cm-task-completed`, then asks **"Restart now?"** → `POST /v2/manager/reboot` on yes. After reconnect: refresh node defs, rebuild index |
| `vaplus_open` | `url, label` | http(s) only | `safe:true`; opens in a new browser tab (VA strips raw URLs from replies) |

**Undo (G4):** before the first structural `run` of a batch, VA+ stores `JSON.stringify(root.serialize())` keyed like VA's `wfKey`, and wraps the batch in `changeTracker.beforeChange()/afterChange()` so **Ctrl+Z is one step**. It also shows a toast: **"VA+ built N things · Undo"**. That restores the stored graph (setGraph(root) if in a subgraph, `root.configure(...)`, `checkState()`). The toast explains that VA's own "Undo" link only reverts settings.

**Guards:**
- A per-batch id ignores a second "Yes" while a batch is running (VA has no busy state).
- Failures inside `run` show a toast naming the failed step. Known limitation: VA's history still records "the user said yes: these changes were made". VA+ mitigates by prefixing the next request with a short "[VA+: step X failed: reason]" note (wrapping `api.fetchApi` for `/lc_vision/assistant/chat` only).

**Recommendation order (prompt rule plus backend ranking):**
1. installed nodes
2. installed LC twins (via the swap map)
3. installed packs' example workflows
4. Manager packs (registry first, then by stars)
5. web results, marked "manual install"

Krea 2 answers should explain which Krea pack is for what (from READMEs) before proposing.

### 5.5 Lonecat ecosystem (must stay intact)

- LC Note's import of `va_tour.js` and its `/lc_vision/translate`, `/lc_vision/write_note`: untouched (VA+ never patches the translator's helpers).
- Tours stay in Lonecat's format and location, and snapshots stay VA's.
- VA+ preserves node ids when it replaces nodes (same approach as LC's update path), so tours and snapshots keep matching. Example workflows open in a new tab, so the current workflow's `extra.vision_assistant` stays intact.
- When carrying values into LC Optimizer, never copy pick markers (`★ Recommended`, `⬇ Download:`, `★ Author:`, `From checkpoint`) as file names.
- **Polish phase (optional):** correct LC System Check's "Vision Assistant chat" line when Venice is on. Do it by wrapping `lc_system_check.run_and_save` with a thread-local "saving" guard (found via `sys.modules`), so the Venice line never gets written into `user/LC123/system_profile.json`.

### 5.6 Settings, key and config

- **ComfyUI settings,** category `LC Settings ⚙️ › Vision Plus` (ids `VAPlus.*`, no collisions with `LCVision.*`, `LC123.*`, `LC.VisionAssistant*`):
  - `VAPlus.Enabled` (default on)
  - `VAPlus.Model` (combo from `/va_plus/models`, a cached Venice `/models` list filtered to text models with function calling)
  - `VAPlus.WebSearch` (default on, capped at 2 per answer)
  - `VAPlus.ShowCost` (default on)
  - a **Venice key** button (status: set / not set)
- **Key:** `POST /va_plus/key` (write-only; never returned to the page). Stored in `ComfyUI/user/default/va_plus/secrets.json` (outside workflows and outside `comfy.settings.json`). Falls back to the `VENICE_API_KEY` env var. Never logged.
- **Config the backend can read** (needed in worker threads): the page mirrors `Enabled`, `Model` and `WebSearch` to `POST /va_plus/config` → `user/default/va_plus/config.json`.
- **LAN safety:** VA+ adds no endpoint that installs, reboots or returns secrets. Installs and reboots are page-side calls to the Manager after a user click. `/va_plus/config` validates its input.

### 5.7 VA+ status line and toasts

A slim line under VA's chat box (mounted by VA+ page code next to `.va`) shows "VA+ · Venice · <model> · $0.0123 this session". If something is wrong it says "VA+ off: key missing", "VA+ off: Vision Assistant changed" or "Building off: restart to re-enable". Toasts are used for build results, undo, install progress and the restart prompt. Strings use VA's i18n (`va_i18n`) where possible; English first.

## 6. Privacy and cost

- **Leaves the machine when VA+ is on:**
  - to Venice: chat turns, VA's workflow context (summary, notes, checkup), knowledge search hits, node info, relevant model file names for carry-over
  - to Venice augment: web search queries
- **Only after a yes:** Manager install traffic (comfy.org, GitHub).
- **Never:** the key to the browser, logs or URLs; data to any other server; VA+ adds no telemetry.
- Both default models are marked private (no retention) in Venice's catalog. Still, this changes VA's local-only design, and the README says so plainly.
- **Typical cost:** a plain chat turn is around $0.002 to $0.01. A build answer with tools and one web search is around $0.02 to $0.04. The status line shows the running total.

## 7. Documentation deliverables (G6)

All in the repo, mirrored to a Notion page:
- `README.md`: what it is, install, set key, use, the Krea 2 edit and two-LoRA walkthroughs, uninstall
- `docs/architecture.md`: this design, kept current
- `docs/hook.md`: the one-line hook, installer behaviour, what happens on LC updates, manual re-apply and removal
- `docs/actions.md`: every `vaplus_*` action with fields, checks and examples
- `docs/knowledge.md`: index sources, tokenizer, ranking, tool loop
- `docs/privacy-and-cost.md`
- `docs/troubleshooting.md`: key errors, 409 busy, hook missing, Manager security level blocking installs, Desktop restart behaviour
- `CHANGELOG.md`
- `LICENSE` (MIT, with LC Vision credit)
- this spec and the implementation plan under `docs/superpowers/`

## 8. Testing

- **Python (pytest, run with the ComfyUI venv):**
  - VA module discovery (fake `sys.modules`), patch idempotence and fail-closed
  - routing rule
  - request builder (no llama fields, `venice_parameters`, reasoning effort)
  - `strictify(TOUR_SCHEMA)`
  - error mapping, no retry on 4xx
  - tool-loop bounds and reasoning round-trip (mocked HTTP)
  - BM25 index and tokenizer, Krea 2 synonym queries
  - Manager cache parsing, install payload builder
  - hook installer (exact match, CRLF, idempotent, backup, refuses on mismatch)
  - carry-over mapper (`control_after_generate`, V1/V3 combos, subgraphs, pick markers)
- **JS (node --test on pure helpers):** action validation, ref resolution, slot matching, batch packing.
- **Manual acceptance in ComfyUI:**
  1. A chat reply via Venice; "where is the sampler?" glows and zooms.
  2. A guided tour builds on the 10 GB card and saves; LC Optimizer still reads author picks.
  3. Krea 2 image-to-image edit: right pack and nodes explained, example opened in a new tab with the user's models and prompts carried over, runs.
  4. Two-LoRA regional: proposes the Regional MultiLoRA setup, builds it after yes, one Undo removes it.
  5. Bolt-on: add an upscaler and wire it; Ctrl+Z is one step.
  6. Install flow on a small harmless pack: yes → install → restart prompt → nodes available.
  7. VA+ off, and VA+ folder removed: VA identical to today; LC Note translate unaffected.
  8. The LC Vision update simulation (hook removed) is re-applied at next start.

## 9. Phases (each shippable)

1. **Brain:** pack skeleton, settings, key, config, VA discovery and patch, Venice chat, tours, status middleware, errors, cost line. *VA works on Venice; tours unlock.*
2. **Knowledge (read-only):** index, tool loop, web search, recommendations with highlight and `vaplus_open`. *VA+ recommends but doesn't build.*
3. **Building:** hook and installer, `VAPlus.vet`, add, connect, batch, load-example and carry-over, undo, guards.
4. **Installing:** Manager install, restart, re-index.
5. **Polish:** LC System Check line, docs pass, optional opt-in Venice for LC Note translate and spelling.

## 10. Left to the builder

BM25 parameters and synonym table contents; exact prompt wording of the VA+ addendum; toast and status-line styling; file layout inside the pack; how the Venice model list is filtered; streaming vs non-streaming for chat; tuning of timeouts and caps; node placement algorithm; test fixtures.

## 11. Known limitations (documented, accepted)

- VA's own Undo link and its local-model labels and tooltip are VA's; with Venice on, VA+ explains the difference in its toast and status line instead of editing VA.
- A registry update of LC Vision removes the hook until the next restart.
- Packs that are neither in the Comfy Registry nor in the Manager list can't be installed by VA+; it offers an open-link instead.
- Brand-new model families depend on README and web quality; VA+ says when it's guessing.

## 12. Open items for the user

- How the repo reaches GitHub: `gh` CLI isn't installed and the GitHub connector isn't authorized. Options: install `gh` (winget) and sign in, or authorize the GitHub connector via /mcp, or create an empty repo yourself and VA+ gets pushed to it. Also public or private.
- Notion location: default is a private draft page, moveable later.
