# Changelog

## 0.1.0: Phase 1 (Brain), 2026-11-23

- Vision Assistant's chat and guided tours answer from a Venice model when VA+ is on, with no VRAM use. Tours now work on any card.
- Settings under **LC Settings ⚙️ › Vision Plus**, a **VA+: Set Venice API key** command (write-only key, stored on this PC), and a status line with the session cost.
- A local model picked in LC Settings always wins. VA+ steps aside if LC Vision changes.
- Plain-language Venice errors. Rejected requests are never retried. Falls back to `venice-uncensored-1-2` if the chosen model is retired.
