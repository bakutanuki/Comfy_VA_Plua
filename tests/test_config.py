from vaplus.config import DEFAULTS, Store


def test_defaults(tmp_path):
    assert Store(tmp_path).load() == DEFAULTS


def test_save_validates(tmp_path):
    cfg = Store(tmp_path).save({"enabled": "yes", "model": 5, "junk": 1})
    assert cfg["enabled"] is True
    assert cfg["model"] == DEFAULTS["model"]
    assert "junk" not in cfg
    assert Store(tmp_path).load() == cfg


def test_save_accepts_valid(tmp_path):
    cfg = Store(tmp_path).save({"enabled": False, "model": "venice-uncensored-1-2"})
    assert cfg["enabled"] is False and cfg["model"] == "venice-uncensored-1-2"


def test_key_roundtrip_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VENICE_API_KEY", raising=False)
    s = Store(tmp_path)
    assert s.get_key() is None and not s.has_key()
    s.set_key("abc")
    assert s.get_key() == "abc" and s.has_key()
    s.set_key("")
    assert s.get_key() is None
    monkeypatch.setenv("VENICE_API_KEY", "env")
    assert s.get_key() == "env"


def test_key_not_in_config(tmp_path):
    s = Store(tmp_path)
    s.set_key("abc")
    s.save({"enabled": True})
    assert "abc" not in (tmp_path / "config.json").read_text()
