import io
from PIL import Image
TOKEN='event-a-token-123456789012345678901234'


def configure(client,headers,**settings):
    response=client.patch(f'/api/admin/events/{TOKEN}',headers=headers,json=settings)
    assert response.status_code==200,response.text
    return response.json()


def photo(client,headers):
    stream=io.BytesIO();Image.new('RGB',(20,20),'red').save(stream,format='JPEG')
    result=client.post(f'/api/events/{TOKEN}/photos',data={'uploader_name':'Deniz'},files=[('files',('photo.jpg',stream.getvalue(),'image/jpeg'))])
    pid=result.json()['uploaded'][0]['id']
    assert client.patch(f'/api/admin/photos/{pid}',headers=headers,json={'status':'approved'}).status_code==200
    return pid


def test_code_blocks_all_public_data_and_media_and_rotates(client,admin_headers):
    pid=photo(client,admin_headers)
    meta=configure(client,admin_headers,access_code='TestCode123')
    assert meta['access_code_enabled'] and 'access_code_hash' not in meta and 'access_code' not in meta
    paths=['','/invitation','/messages','/photos','/cover','/music','/upload-qr']
    for path in paths:assert client.get(f'/api/events/{TOKEN}{path}').status_code==423,path
    assert client.get(f'/api/photos/{pid}?access={TOKEN}').status_code==423
    assert client.get(f'/api/photos/{pid}/thumbnail?access={TOKEN}').status_code==423
    assert client.get(f'/api/photos/{pid}?access={TOKEN}',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.post(f'/api/events/{TOKEN}/rsvp',json={'name':'Deniz','email':'deniz@example.com','status':'attending'}).status_code==423
    assert client.post(f'/api/events/{TOKEN}/messages',json={'name':'Deniz','message':'Merhaba'}).status_code==423
    assert client.post(f'/api/events/{TOKEN}/unlock',json={'code':'wrong'}).status_code==403
    response=client.post(f'/api/events/{TOKEN}/unlock',json={'code':'TestCode123'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==200
    assert client.get(f'/api/photos/{pid}?access={TOKEN}').status_code==200
    configure(client,admin_headers,access_code='Changed123')
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==423
    assert client.get(f'/api/admin/events/{TOKEN}/invitation',headers=admin_headers).status_code==200
    assert client.post(f'/api/admin/events/{TOKEN}/access-preview').status_code==401
    assert client.post(f'/api/admin/events/{TOKEN}/access-preview',headers=admin_headers).status_code==200
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==200
    configure(client,admin_headers,access_code='')
    client.cookies.clear()
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==200


def test_private_album_blocks_original_and_thumb_but_allows_uploads(client,admin_headers):
    pid=photo(client,admin_headers)
    configure(client,admin_headers,album_public=False)
    assert client.get(f'/api/events/{TOKEN}/photos').json()==[]
    for suffix in ['', '/thumbnail']:
        assert client.get(f'/api/photos/{pid}{suffix}?access={TOKEN}').status_code==404
        assert client.get(f'/api/photos/{pid}{suffix}',headers=admin_headers).status_code==200
    assert client.get(f'/api/admin/events/{TOKEN}/album.zip',headers=admin_headers).status_code==200
    configure(client,admin_headers,album_public=True)
    assert client.get(f'/api/photos/{pid}?access={TOKEN}').status_code==200


def test_unlock_rate_limit_expiry_and_owner_isolation(client,admin_headers,monkeypatch):
    configure(client,admin_headers,access_code='TestCode123')
    other=client.post('/api/admin/register',json={'email':'other@test.com','password':'OtherPassword123!'}).json()
    assert client.post(f'/api/admin/events/{TOKEN}/access-preview',headers={'Authorization':f'Bearer {other["access_token"]}'}).status_code==404
    assert client.post(f'/api/events/{TOKEN}/unlock',json={'code':'TestCode123'}).status_code==200
    from app.api import event_access
    now=event_access.time.time()
    monkeypatch.setattr(event_access.time,'time',lambda:now+event_access.TTL+1)
    assert client.get(f'/api/events/{TOKEN}').status_code==423
    for _ in range(4):assert client.post(f'/api/events/{TOKEN}/unlock',json={'code':'wrong'}).status_code==403
    assert client.post(f'/api/events/{TOKEN}/unlock',json={'code':'wrong'}).status_code==429


def test_invalid_code_and_settings_keep_existing_code(client,admin_headers):
    assert client.patch(f'/api/admin/events/{TOKEN}',headers=admin_headers,json={'access_code':'short'}).status_code==422
    configure(client,admin_headers,access_code='TestCode123')
    configure(client,admin_headers,album_public=False)
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code==423


def test_guest_media_never_issues_storage_signed_url(client,admin_headers,monkeypatch):
    pid=photo(client,admin_headers)
    from app.services.photo_service import PhotoService
    def forbidden(*args,**kwargs):raise AssertionError('Guest must use the checked proxy')
    monkeypatch.setattr(PhotoService,'signed_access_url',forbidden)
    for suffix in ['', '/thumbnail']:
        assert client.get(f'/api/photos/{pid}{suffix}?access={TOKEN}',headers={'Authorization':'unrecognized'}).status_code==200
