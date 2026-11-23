# VA+ (Vision Assistant Plus)

VA+ runs **Vision Assistant** (from [LC Vision](https://github.com/lonecatone23) by Lonecat) on a **Venice.ai** model instead of a local model in your GPU.

- **No VRAM used** by the assistant.
- **Guided tours unlock on any card.** Building a tour used to need a 20 GB+ card.
- **Uncensored model by default** (`deepseek-v4-1-flash-1017-uncensored`).
- Everything Vision Assistant does stays the same: glowing nodes, zooming, checkups, one-click fixes, snapshots and tours.

> **Status: Phase 1 (Brain).** Coming next: node and pack recommendations (Phase 2), building on the canvas (Phase 3), installing packs through the Manager (Phase 4). See [the design](docs/superpowers/specs/2026-11-23-va-plus-design.md).

## Requirements

- ComfyUI with **LC Vision** (`ComfyUI_LC_Vision_nodes`) installed.
- A **Venice API key** (venice.ai › Settings › API).
- No extra Python packages.

## Install

```powershell
cd <ComfyUI>\custom_nodes
git clone https://github.com/bakutanuki/Comfy_VA_Plua.git ComfyUI_VA_Plus
```

Restart ComfyUI. The log shows `[VA+] Vision Assistant: patched`.

## Set up

1. Open the command palette (Ctrl+Shift+P) and run **VA+: Set Venice API key**. You can also click **key** in the VA+ line under Vision Assistant's chat.
2. Optional settings are under **Settings › LC Settings ⚙️ › Vision Plus**:

| Setting | Default | What it does |
|---|---|---|
| Use Venice for Vision Assistant | on | Turn VA+ off to go back to the local model |
| Venice model | `deepseek-v4-1-flash-1017-uncensored` | `venice-uncensored-1-2` is cheaper and more permissive |
| Allow web search for new packs | on | Used from Phase 2, max 2 searches per answer |
| Show cost in the status line | on | Shows the running cost for this session |

## Use

Use Vision Assistant as usual. The line under its chat shows `VA+ · Venice · <model> · $0.0123 this session`.

**Back to local:** pick a local model in **LC Settings › Vision › Chat model** (that choice always wins), or switch VA+ off. Setting LC's chat model to **Off** turns the chat off, Venice included.

## Uninstall

Delete the `ComfyUI_VA_Plus` folder and restart ComfyUI. Vision Assistant goes back to exactly how it was.

## Docs

- [Architecture](docs/architecture.md)
- [Privacy and cost](docs/privacy-and-cost.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Changelog](CHANGELOG.md)

## Credits

Vision Assistant and LC Vision are by **lonecatone23** (MIT). VA+ contains none of their code; it plugs into the installed pack. VA+ is MIT licensed.
