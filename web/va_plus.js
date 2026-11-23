// VA+ page code: settings, the write-only Venice key prompt, and a status line under Vision Assistant's chat.
// The key is sent once to /va_plus/key and never stored in settings or localStorage.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CATEGORY = ["LC Settings ⚙️", "Vision Plus"];
const MODELS = ["deepseek-v4-1-flash-1017-uncensored", "venice-uncensored-1-2"];

const setting = (id) => app.extensionManager?.setting?.get?.(id);
const post = (path, body) =>
  api.fetchApi(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function syncConfig() {
  return post("/va_plus/config", {
    enabled: setting("VAPlus.Enabled") ?? true,
    model: setting("VAPlus.Model") || MODELS[0],
    web_search: setting("VAPlus.WebSearch") ?? true,
    show_cost: setting("VAPlus.ShowCost") ?? true,
  }).catch(() => {});
}

// Comfy Desktop (Electron) blocks window.prompt, so the key gets its own small dialog.
function askKey() {
  document.querySelector(".vaplus-key")?.remove();
  const box = document.createElement("div");
  box.className = "vaplus-key";
  box.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center";
  box.innerHTML = `<div style="background:var(--comfy-menu-bg,#222);color:var(--fg-color,#ddd);padding:16px;border-radius:8px;width:380px;font-size:13px">
      <div style="font-weight:600;margin-bottom:8px">Venice API key</div>
      <input type="password" placeholder="Paste key (empty = remove)" style="width:100%;box-sizing:border-box;padding:6px" autocomplete="off">
      <div style="opacity:.7;margin:6px 0 10px">Stored on this PC only. Never shown again or sent anywhere except Venice.</div>
      <div class="msg" style="min-height:16px;margin-bottom:8px"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end"><button data-x>Cancel</button><button data-s>Save</button></div></div>`;
  const input = box.querySelector("input"), msg = box.querySelector(".msg");
  const close = () => box.remove();
  const save = async () => {
    try {
      const j = await (await post("/va_plus/key", { key: input.value.trim() })).json();
      msg.textContent = j.has_key ? "Saved." : "Key removed.";
      refreshStatus();
      setTimeout(close, 700);
    } catch (_) {
      msg.textContent = "Couldn't save the key.";
    }
  };
  box.querySelector("[data-x]").onclick = close;
  box.querySelector("[data-s]").onclick = save;
  box.addEventListener("click", (e) => e.target === box && close());
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") close(); });
  document.body.appendChild(box);
  input.focus();
}

let statusEl = null;
async function refreshStatus() {
  if (!statusEl?.isConnected) return;
  try {
    const s = await (await api.fetchApi("/va_plus/status")).json();
    let text;
    if (s.patch === "changed") text = "VA+ off: Vision Assistant changed";
    else if (s.patch !== "patched" && s.patch !== "already") text = "VA+ off: Vision Assistant not found";
    else if (!s.enabled) text = "VA+ off";
    else if (!s.has_key) text = "VA+ off: key missing";
    else text = `VA+ · Venice · ${s.model}${setting("VAPlus.ShowCost") === false ? "" : ` · $${(s.cost_usd || 0).toFixed(4)} this session`}`;
    if (s.status) text += ` · ${s.status}`;
    if (s.last_error) text += ` · ⚠ ${s.last_error}`;
    statusEl.querySelector("span").textContent = text;
  } catch (_) {
    statusEl.querySelector("span").textContent = "VA+ status unavailable";
  }
}

function mountStatus() {
  const va = document.querySelector(".va");
  if (!va || (statusEl?.isConnected && statusEl.previousElementSibling === va)) return;
  statusEl?.remove();
  statusEl = document.createElement("div");
  statusEl.className = "vaplus-status";
  statusEl.style.cssText = "font-size:11px;opacity:.75;padding:4px 8px;display:flex;gap:8px;align-items:center";
  statusEl.innerHTML = `<span>VA+ …</span><a href="#" style="margin-left:auto">key</a>`;
  statusEl.querySelector("a").addEventListener("click", (e) => { e.preventDefault(); askKey(); });
  va.after(statusEl);
  refreshStatus();
}

app.registerExtension({
  name: "VAPlus.Settings",
  settings: [
    { id: "VAPlus.Enabled", category: [...CATEGORY, "Enabled"], name: "Use Venice for Vision Assistant", type: "boolean", defaultValue: true,
      tooltip: "On: VA's chat and guided tours answer from Venice (no VRAM). Picking a local model in LC Settings > Vision still wins.", onChange: syncConfig },
    { id: "VAPlus.Model", category: [...CATEGORY, "Model"], name: "Venice model", type: "combo", options: MODELS, defaultValue: MODELS[0], onChange: syncConfig },
    { id: "VAPlus.WebSearch", category: [...CATEGORY, "WebSearch"], name: "Allow web search for new packs (max 2 per answer)", type: "boolean", defaultValue: true, onChange: syncConfig },
    { id: "VAPlus.ShowCost", category: [...CATEGORY, "ShowCost"], name: "Show cost in the status line", type: "boolean", defaultValue: true,
      onChange: () => { syncConfig(); refreshStatus(); } },
  ],
  commands: [{ id: "VAPlus.SetKey", label: "VA+: Set Venice API key", function: askKey }],
  async setup() {
    syncConfig();
    new MutationObserver(() => mountStatus()).observe(document.body, { childList: true, subtree: true });
    mountStatus();
    setInterval(refreshStatus, 30000);
  },
});

// VA's chat and tour requests: ComfyUI's page aborts any fetch after 60 s ("Fetch timeout"), but a Venice answer can take
// longer (a tour of a big workflow especially), so give them 3 minutes. Also refresh the cost line after each answer.
const VA_CALL = /\/lc_vision\/assistant\/(chat|tour)/;
const origFetch = api.fetchApi.bind(api);
api.fetchApi = async (path, opts) => {
  const isVA = typeof path === "string" && VA_CALL.test(path);
  const r = await origFetch(path, isVA ? { ...(opts || {}), timeoutMs: 180000 } : opts);
  if (isVA) setTimeout(refreshStatus, 300);
  return r;
};
