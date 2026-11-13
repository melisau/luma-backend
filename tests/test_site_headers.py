from app.main import site_headers


def test_landing_is_indexable_with_csp():
    headers = site_headers("/")
    assert "X-Robots-Tag" not in headers
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-cache"


def test_editor_and_invitations_stay_out_of_search():
    assert "noindex" in site_headers("/app.html")["X-Robots-Tag"]
    invitation = site_headers("/e/some-token")
    assert "Content-Security-Policy" in invitation
    # Private cache rules for /e/ come from PRIVATE_HEADERS, not here.
    assert "Cache-Control" not in invitation


def test_static_files_are_cached():
    assert "max-age=2592000" in site_headers("/assets/images/wedding-hero.webp")["Cache-Control"]
    assert "max-age=86400" in site_headers("/css/styles.css")["Cache-Control"]
    assert "max-age=86400" in site_headers("/js/main.js")["Cache-Control"]


def test_api_is_left_alone():
    assert site_headers("/api/admin/me") == {}
