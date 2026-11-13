from app.core import security
from app.core.config import get_settings

# Made with the old passlib/bcrypt setup and python-jose; existing users must keep working.
LEGACY_HASH = "$2b$12$hCjd2glN8lv/TB4nE1oXJOVOsnM8aZ1e3Bv4wkBfeKMGd.WpbTUDG"
LEGACY_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJhZG1pbi0xIiwidmVyIjowLCJzY29wZSI6ImFkbWluIiwiZXhwIjo0MTAyNDQ0ODAwfQ."
    "iQC7B92cET-VFHVmUc-0aMVWaHChQrN_2MP0GArNCCg"
)


def test_legacy_password_hash_still_verifies():
    assert security.verify_password("legacy-password-123", LEGACY_HASH)
    assert not security.verify_password("wrong-password", LEGACY_HASH)


def test_long_passwords_match_old_truncation():
    long_password = "x" * 100
    hashed = security.hash_password(long_password)
    assert security.verify_password(long_password, hashed)
    assert security.verify_password("x" * 72, hashed)


def test_invalid_hash_returns_false():
    assert not security.verify_password("anything", "not-a-bcrypt-hash")


def test_legacy_jose_token_decodes(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "legacy-secret-key")
    get_settings.cache_clear()
    try:
        assert security.decode_admin_token(LEGACY_TOKEN) == ("admin-1", 0)
    finally:
        get_settings.cache_clear()


def test_token_round_trip_and_tamper():
    token = security.create_admin_token("admin-2", 3)
    assert security.decode_admin_token(token) == ("admin-2", 3)
    assert security.decode_admin_token(token[:-2] + "xx") is None
