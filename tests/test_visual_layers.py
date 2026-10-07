from io import BytesIO
from PIL import Image

TOKEN = "event-a-token-123456789012345678901234"

def test_transparent_layers_upload_persist_access_and_cleanup(client, admin_headers):
    image = BytesIO()
    Image.new("RGBA", (50, 60), (120, 20, 30, 0)).save(image, "PNG")
    upload_url = f"/api/admin/events/{TOKEN}/invitation/visual-assets"
    assert client.post(upload_url, files={"file": ("layer.png", image.getvalue(), "image/png")}).status_code == 401
    response = client.post(upload_url, headers=admin_headers, files={"file": ("layer.png", image.getvalue(), "image/png")})
    assert response.status_code == 200
    asset = response.json()
    streamed = client.get(asset["src"])
    assert streamed.status_code == 200
    assert Image.open(BytesIO(streamed.content)).getpixel((0, 0))[3] == 0
    layer = {"id": asset["id"], "position": "hero-foreground", "frame": "gold", "motion": "sway", "caption": "Birthday", "placement": "bottom-right", "background_fit": "repeat"}
    url = f"/api/admin/events/{TOKEN}/invitation"
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [layer]}).status_code == 200
    client.patch(url, headers=admin_headers, json={"tagline": "Party"})
    public = client.get(f"/api/events/{TOKEN}/invitation").json()["visual_layers"]
    assert public[0]["src"] == asset["src"]
    assert public[0]["placement"] == "bottom-right"
    assert public[0]["frame"] == "gold"
    assert public[0]["background_fit"] == "repeat"
    assert public[0]["motion"] == "sway"
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "id": "f" * 32}]}).status_code == 400
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "motion": "script"}]}).status_code == 422
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "placement": "outside"}]}).status_code == 422
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [layer] * 33}).status_code == 422
    for position in ["invitation-background", "opening-background", "story-background", "details-background", "memories-background", "exhibition-background", "countdown-background", "footer-background"]:
        assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "position": position}]}).status_code == 200
        assert client.get(f"/api/events/{TOKEN}/invitation").json()["visual_layers"][0]["position"] == position
    assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "background_fit": "invalid"}]}).status_code == 422
    for motion in ["slide-right", "slide-left", "across-right", "across-left", "unfold-right", "unfold-left", "spin", "spin-away", "fade-away"]:
        assert client.patch(url, headers=admin_headers, json={"visual_layers": [{**layer, "position": "sticker-details", "motion": motion, "width": 10}]}).status_code == 200
        sticker = client.get(f"/api/events/{TOKEN}/invitation").json()["visual_layers"][0]
        assert sticker["position"] == "sticker-details" and sticker["motion"] == motion and sticker["width"] == 10
    assert client.patch(url, headers=admin_headers, json={"visual_layers": []}).status_code == 200
    assert client.get(asset["src"]).status_code == 404

def test_layer_upload_rejects_non_image(client, admin_headers):
    response = client.post(f"/api/admin/events/{TOKEN}/invitation/visual-assets", headers=admin_headers, files={"file": ("x.png", b"invalid", "image/png")})
    assert response.status_code == 400
