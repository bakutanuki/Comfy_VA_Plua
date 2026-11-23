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

async function askKey() {
  const key = window.prompt("Paste your Venice API key (leave empty to remove it). It is stored on this PC only.");
  if (key === null) return;
  try {
    const r = await post("/va_plus/key", { key: key.trim() });
    const j = await r.json();
    alert(j.has_key ? "Venice key saved." : "Venice key removed.");
  } catch (_) {
    alert("Couldn't save the key.");
  }
  refreshStatus();
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

// refresh the cost after each VA chat or tour answer
const origFetch = api.fetchApi.bind(api);
api.fetchApi = async (path, opts) => {
  const r = await origFetch(path, opts);
  if (typeof path === "string" && /\/lc_vision\/assistant\/(chat|tour)/.test(path)) setTimeout(refreshStatus, 300);
  return r;
};
