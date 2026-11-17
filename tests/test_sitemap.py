"""B3: the landing page has a sitemap that robots.txt points to."""
from pathlib import Path

import pytest

FRONTEND = Path(__file__).parents[2] / "luma-frontend"


@pytest.mark.skipif(not (FRONTEND / "sitemap.xml").is_file(), reason="needs the luma-frontend checkout")
def test_sitemap_and_robots_are_served(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setattr(main, "frontend_dir", FRONTEND)
    client = TestClient(main.app)
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>https://luma.melisauyar.com/</loc>" in sitemap.text
    assert "Sitemap: https://luma.melisauyar.com/sitemap.xml" in client.get("/robots.txt").text


def test_missing_sitemap_is_404(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setattr(main, "frontend_dir", tmp_path)
    assert TestClient(main.app).get("/sitemap.xml").status_code == 404
