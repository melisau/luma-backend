from urllib.parse import urlparse

from app.services.storage import S3CompatibleStorage


def _storage(public_endpoint=None):
    return S3CompatibleStorage(
        endpoint="http://seaweedfs:8333",
        bucket="luma-private",
        access_key="key",
        secret_key="secret",
        region="us-east-1",
        public_endpoint=public_endpoint,
    )


def test_signed_links_use_public_address():
    url = urlparse(_storage("https://luma.example.com").create_signed_url("events/a/photo.jpg", 300))
    assert url.scheme == "https"
    assert url.netloc == "luma.example.com"
    # Path style keeps the link on the one domain Caddy serves.
    assert url.path == "/luma-private/events/a/photo.jpg"
    assert "X-Amz-Signature=" in url.query


def test_signed_links_default_to_internal_endpoint():
    url = urlparse(_storage().create_signed_url("photo.jpg", 300))
    assert url.netloc == "seaweedfs:8333"
