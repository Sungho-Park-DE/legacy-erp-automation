from app import flags, settings


def test_flags_default_off(monkeypatch):
    monkeypatch.delenv("LEA_FLAG_SAVE", raising=False)
    assert not flags.is_enabled("save")
    monkeypatch.setenv("LEA_FLAG_SAVE", "1")
    assert flags.is_enabled("save")


def test_policy_values_present():
    assert settings.SIGHTING_NEEDED >= 2
