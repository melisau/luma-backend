"""B1: fonts are served from our own origin; the CSP no longer allows Google Fonts."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_csp_allows_only_own_fonts_and_styles():
    from app.main import CONTENT_SECURITY_POLICY
    assert "googleapis" not in CONTENT_SECURITY_POLICY
    assert "gstatic" not in CONTENT_SECURITY_POLICY
    assert "font-src 'self'" in CONTENT_SECURITY_POLICY


def test_backend_and_frontend_csp_match():
    from app.main import CONTENT_SECURITY_POLICY
    headers = ROOT.parent / "luma-frontend" / "_headers"
    if headers.is_file():
        assert f"Content-Security-Policy: {CONTENT_SECURITY_POLICY}" in headers.read_text(encoding="utf-8")
