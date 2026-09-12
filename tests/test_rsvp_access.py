TOKEN="event-a-token-123456789012345678901234"
PAYLOAD={"name":"Deniz","email":"deniz@example.com","status":"attending","notes":"Özel not"}


def test_existing_response_requires_secret(client,admin_headers):
    url=f"/api/events/{TOKEN}/rsvp"
    first=client.post(url,json=PAYLOAD)
    assert first.status_code==200
    assert first.headers['cache-control']=='no-store'
    token=first.json()['edit_token']
    assert client.post(url,json={**PAYLOAD,'status':'declined'}).status_code==403
    assert client.post(url,json={**PAYLOAD,'edit_token':'x'*43}).status_code==403
    updated=client.post(url,json={**PAYLOAD,'status':'declined','edit_token':token})
    assert updated.json()['status']=='declined'
    assert client.post(url,json={**PAYLOAD,'email':'someone@example.com','edit_token':token}).status_code==403
    guests=client.get(f'/api/admin/events/{TOKEN}/guests',headers=admin_headers).json()
    assert len(guests)==1
    assert 'edit_token' not in guests[0] and 'rsvp_token_hash' not in guests[0]


def test_owner_link_rotation_and_preinvited_guest(client,admin_headers):
    guest=client.post(f'/api/admin/events/{TOKEN}/guests',headers=admin_headers,json=PAYLOAD).json()
    url=f'/api/admin/events/{TOKEN}/guests/{guest["id"]}/rsvp-link'
    assert client.post(url).status_code==401
    assert client.post(f'/api/events/{TOKEN}/rsvp',json=PAYLOAD).status_code==403
    first=client.post(url,headers=admin_headers).json()['edit_token']
    second=client.post(url,headers=admin_headers).json()['edit_token']
    assert first!=second
    assert client.post(f'/api/events/{TOKEN}/rsvp',json={**PAYLOAD,'edit_token':first}).status_code==403
    assert client.post(f'/api/events/{TOKEN}/rsvp',json={**PAYLOAD,'edit_token':second}).status_code==200
    from app.db import database
    from app.db.models import AdminUser, Event
    from app.core.security import hash_password
    with database.SessionLocal() as db:
        other=AdminUser(email='other@test.com',password_hash=hash_password('OtherPass123!'))
        db.add(other);db.flush()
        db.add(Event(admin_id=other.id,name='Other',slug='other',private_token='other-event-token-12345678901234567890'));db.commit()
    assert client.post(f'/api/admin/events/other-event-token-12345678901234567890/guests/{guest["id"]}/rsvp-link',headers=admin_headers).status_code==404
    assert client.post('/api/events/other-event-token-12345678901234567890/rsvp',json={**PAYLOAD,'edit_token':second}).status_code==403
