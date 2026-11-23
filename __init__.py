"""VA+ (Vision Assistant Plus): runs LC Vision's Vision Assistant on a Venice model. See README.md."""
WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

try:
    from server import PromptServer

    from .vaplus import patch, routes
    from .vaplus.config import Store, default_root

    _store = Store(default_root())
    _state = {"patch": patch.ensure_patched(_store)}
    routes.register(PromptServer.instance, _store, _state)

    async def _on_startup(_app):
        # every pack is imported by now, so LC Vision is found even if it loaded after VA+
        _state["patch"] = patch.ensure_patched(_store)
        print(f"[VA+] Vision Assistant: {_state['patch']}")

    PromptServer.instance.app.on_startup.append(_on_startup)
except Exception as e:  # never take ComfyUI down
    print(f"[VA+] disabled: {e}")
