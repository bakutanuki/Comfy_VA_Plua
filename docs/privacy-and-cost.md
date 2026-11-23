# Privacy and cost

## What leaves your PC

With VA+ on, these go **to Venice**:
- your chat messages
- Vision Assistant's workflow context: the summary of your workflow, its notes and checkup items
- the parts list when you build a guided tour

Things that **never** leave your PC:
- The **Venice key** never reaches the browser, a log line or a URL. It's only sent to Venice, in the request header.
- Nothing is sent to any other server, and VA+ adds no telemetry.

From Phase 2, web searches for new packs also go to Venice (max 2 per answer, and you can switch them off). From Phase 4, pack installs contact comfy.org and GitHub, and only after you say yes.

Both default models are marked **private** (no data retention) in Venice's catalog. Still, this changes Vision Assistant's local-only design. Switch VA+ off, or pick a local model, whenever you want everything to stay local.

## Where VA+ stores things

- `ComfyUI/user/default/va_plus/config.json`: settings
- `ComfyUI/user/default/va_plus/secrets.json`: your key. It isn't inside workflows or `comfy.settings.json`. Delete the file to remove the key.

## Cost

Prices are from the live Venice catalog on 2026-11-23, per million tokens:

| Model | Input | Output |
|---|---|---|
| `deepseek-v4-1-flash-1017-uncensored` (default) | $0.33 | $1.32 |
| `venice-uncensored-1-2` | $0.20 | $0.90 |

- A normal chat turn costs about **$0.002 to $0.01**.
- A guided tour of a big workflow costs about **$0.01 to $0.03**.
- From Phase 2, a build answer with lookups and a web search will cost about $0.02 to $0.04.

The VA+ line under the chat shows the running total for the session.
