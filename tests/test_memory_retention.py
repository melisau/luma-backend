import io
from datetime import datetime,timedelta,timezone
from PIL import Image
from app.db import database
from app.db.models import Event,Photo,Guest,GuestbookMessage
from app.services.memory_retention import purge_expired_memories
TOKEN='event-a-token-123456789012345678901234'


def seed_memories(client):
    stream=io.BytesIO();Image.new('RGB',(20,20),'blue').save(stream,format='JPEG')
    photo=client.post(f'/api/events/{TOKEN}/photos',data={'uploader_name':'Deniz'},files=[('files',('photo.jpg',stream.getvalue(),'image/jpeg'))]).json()['uploaded'][0]
    client.post(f'/api/events/{TOKEN}/messages',json={'name':'Deniz','message':'Kalıcı bir anı'})
    client.post(f'/api/events/{TOKEN}/rsvp',json={'name':'Deniz','email':'deniz@example.com','status':'attending'})
    return photo['id']


def test_policy_requires_confirmation_and_can_be_cancelled(client,admin_headers):
    deadline=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    url=f'/api/admin/events/{TOKEN}'
    assert client.patch(url,headers=admin_headers,json={'memory_delete_at':deadline}).status_code==422
    assert client.patch(url,headers=admin_headers,json={'memory_delete_at':datetime.now(timezone.utc).isoformat(),'confirm_memory_deletion':True}).status_code==422
    assert client.patch(url,headers=admin_headers,json={'memory_delete_at':deadline,'confirm_memory_deletion':True}).status_code==200
    assert client.patch(url,headers=admin_headers,json={'memory_delete_at':None}).status_code==200
    seed_memories(client)
    assert purge_expired_memories(datetime.now(timezone.utc)+timedelta(days=3))=={'photos':0,'messages':0}


def test_expired_cleanup_removes_files_messages_but_preserves_invitation_rsvp(client,admin_headers):
    pid=seed_memories(client)
    from app.services.storage import get_storage
    with database.SessionLocal() as db:
        event=db.query(Event).filter(Event.private_token==TOKEN).one()
        event.memory_delete_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        row=db.get(Photo,pid);keys=[row.storage_key_original,row.storage_key_thumb];db.commit()
    assert client.get(f'/api/events/{TOKEN}/photos').status_code==410
    assert client.get(f'/api/events/{TOKEN}/messages').status_code==410
    assert client.get(f'/api/photos/{pid}?access={TOKEN}').status_code==410
    assert client.post(f'/api/events/{TOKEN}/messages',json={'name':'Deniz','message':'Sonra'}).status_code==410
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==200
    assert purge_expired_memories()=={'photos':1,'messages':1}
    assert purge_expired_memories()=={'photos':0,'messages':0}
    with database.SessionLocal() as db:
        assert db.query(Photo).count()==0 and db.query(GuestbookMessage).count()==0
        assert db.query(Guest).count()==1
        assert db.query(Event).one().memory_purged_at is not None
    import pytest
    for key in keys:
        with pytest.raises(FileNotFoundError):get_storage().get_bytes(key)


def test_failed_storage_is_retried_and_unscheduled_memories_remain(client,monkeypatch):
    seed_memories(client)
    assert purge_expired_memories()=={'photos':0,'messages':0}
    with database.SessionLocal() as db:
        event=db.query(Event).filter(Event.private_token==TOKEN).one();event.memory_delete_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    from app.services.storage import LocalPrivateStorage
    original=LocalPrivateStorage.delete
    def fail(*args,**kwargs):raise OSError('offline')
    monkeypatch.setattr(LocalPrivateStorage,'delete',fail)
    assert purge_expired_memories()=={'photos':0,'messages':1}
    with database.SessionLocal() as db:
        assert db.query(Photo).count()==1 and db.query(Event).one().memory_purged_at is None
    monkeypatch.setattr(LocalPrivateStorage,'delete',original)
    assert purge_expired_memories()=={'photos':1,'messages':0}
