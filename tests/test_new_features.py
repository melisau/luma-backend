from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image

from app.db import database as db_module
from app.db.models import AccountToken, AdminUser

TOKEN="event-a-token-123456789012345678901234"

def image_file():
    data=BytesIO();Image.new("RGB",(400,500),(170,80,90)).save(data,"PNG");return {"file":("memory.png",data.getvalue(),"image/png")}

def test_signature_memory_copy_cover_and_scheduled_publish(client,admin_headers):
    response=client.patch(f"/api/admin/events/{TOKEN}/invitation",headers=admin_headers,json={"signature_text":"Ela","memory_title":"Bu gece senin gözünden","memory_text":"Karelerini bizimle paylaş.","language":"tr","design_theme":"celebration"})
    assert response.status_code==200
    assert response.json()["signature_text"]=="Ela"
    assert response.json()["memory_title"]=="Bu gece senin gözünden"
    upload=client.post(f"/api/admin/events/{TOKEN}/invitation/memory-cover",headers=admin_headers,files=image_file())
    assert upload.status_code==200 and upload.json()["memory_cover_url"]
    assert client.get(f"/api/events/{TOKEN}/memory-cover").status_code==200
    future=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    assert client.patch(f"/api/admin/events/{TOKEN}",headers=admin_headers,json={"publish_at":future}).status_code==200
    assert client.get(f"/api/events/{TOKEN}").status_code==403
    assert client.get(f"/api/admin/events/{TOKEN}/invitation",headers=admin_headers).status_code==200

def test_groups_tables_and_collaborator_roles(client,admin_headers):
    guest=client.post(f"/api/admin/events/{TOKEN}/guests",headers=admin_headers,json={"name":"Masa Misafiri","email":"masa@test.com","group_name":"Aile","table_name":"Masa 2"})
    assert guest.status_code==201 and guest.json()["group_name"]=="Aile"
    other=client.post("/api/admin/register",json={"email":"editor@test.com","password":"password123"})
    editor_headers={"Authorization":f"Bearer {other.json()['access_token']}"}
    added=client.post(f"/api/admin/events/{TOKEN}/members",headers=admin_headers,json={"email":"editor@test.com","role":"editor"})
    assert added.status_code==201
    assert client.get(f"/api/admin/events/{TOKEN}/guests",headers=editor_headers).status_code==200
    assert client.post(f"/api/admin/events/{TOKEN}/guests",headers=editor_headers,json={"name":"Editör","email":"new@test.com"}).status_code==201
    assert client.delete(f"/api/admin/events/{TOKEN}",headers=editor_headers).status_code==404

def test_password_reset_and_email_verification_tokens(client):
    registered=client.post("/api/admin/register",json={"email":"mail@test.com","password":"password123"})
    assert registered.status_code==201
    db=db_module.SessionLocal()
    try:
        admin=db.query(AdminUser).filter(AdminUser.email=="mail@test.com").one()
        verify=db.query(AccountToken).filter(AccountToken.admin_id==admin.id,AccountToken.purpose=="verify").one()
        # Stored values are hashes, never usable links.
        assert len(verify.token_hash)==64
    finally: db.close()
    response=client.post("/api/admin/password-reset/request",json={"email":"mail@test.com"})
    assert response.status_code==202
    assert client.post("/api/admin/password-reset/request",json={"email":"missing@test.com"}).status_code==202
