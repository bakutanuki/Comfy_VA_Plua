# Troubleshooting

| What you see | Why | Fix |
|---|---|---|
| `VA+ off: key missing` | No Venice key set | Run **VA+: Set Venice API key** (Ctrl+Shift+P), or set the `VENICE_API_KEY` environment variable |
| "Your Venice key was rejected…" | The key is wrong or revoked | Set it again |
| "Your Venice balance is empty." | No credit | Top up on venice.ai |
| "Venice is rate-limiting you. Wait a minute." | Too many requests | Wait. VA+ never retries rejected requests, so the key doesn't get locked |
| "Venice didn't answer. Try again." | Venice was down or slow (60 s per call, one retry) | Ask again |
| "…is gone from Venice; using the fallback…" | Venice retired your chosen model | Pick another model in Settings › Vision Plus |
| "Still answering the last message." | Vision Assistant handles one question at a time | Wait for the answer |
| `VA+ off: Vision Assistant changed` | An LC Vision update renamed what VA+ plugs into. VA+ steps aside so nothing breaks | Update VA+, or report it |
| `VA+ off: Vision Assistant not found` | LC Vision isn't installed or failed to load | Install or repair LC Vision, then restart |
| Answers still come from the local model | A local model is picked in LC Settings › Vision › Chat model (that choice wins), or VA+ is switched off | Set Chat model to **Auto** and turn VA+ on |
| Vision Assistant's labels mention VRAM or GB | Those labels belong to Vision Assistant. VA+ doesn't edit them | The VA+ line under the chat shows what is really answering |

**Check from a browser:** open `http://127.0.0.1:8188/va_plus/status`. `"patch": "patched"` means VA+ is plugged in.

**Turn VA+ off without uninstalling:** Settings › LC Settings ⚙️ › Vision Plus › *Use Venice for Vision Assistant* → off.
