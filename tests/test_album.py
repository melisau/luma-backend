import io
import zipfile
from PIL import Image
TOKEN='event-a-token-123456789012345678901234'


def image_bytes(size=(800,600)):
    stream=io.BytesIO();Image.new('RGB',size,'red').save(stream,format='JPEG');return stream.getvalue()


def upload(client,raw):
    return client.post(f'/api/events/{TOKEN}/photos',data={'uploader_name':'Deniz'},files=[('files',('image.jpg',raw,'image/jpeg'))])


def test_dedup_resize_delete_and_archive(client,admin_headers,monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(),'max_photo_dimension',600)
    raw=image_bytes()
    first=upload(client,raw);assert first.status_code==200
    photo_id=first.json()['uploaded'][0]['id']
    again=upload(client,raw);assert again.status_code==200
    assert again.json()['uploaded']==[] and again.json()['duplicates_skipped']==1
    url=f'/api/admin/events/{TOKEN}/album.zip'
    assert client.get(url).status_code==401
    response=client.get(url,headers=admin_headers);assert response.status_code==200
    archive=zipfile.ZipFile(io.BytesIO(response.content));assert len(archive.namelist())==1
    with Image.open(io.BytesIO(archive.read(archive.namelist()[0]))) as image:
        assert image.size==(600,450)
    assert response.headers['cache-control']=='private, no-store'
    assert client.delete(f'/api/admin/photos/{photo_id}',headers=admin_headers).status_code==204
    assert client.get(url,headers=admin_headers).status_code==404
    assert len(upload(client,raw).json()['uploaded'])==1


def test_batch_duplicate_and_invalid_upload_is_atomic(client,admin_headers):
    raw=image_bytes()
    response=client.post(f'/api/events/{TOKEN}/photos',data={'uploader_name':'Deniz'},files=[('files',('one.jpg',raw,'image/jpeg')),('files',('two.jpg',raw,'image/jpeg'))])
    assert len(response.json()['uploaded'])==1
    assert response.json()['duplicates_skipped']==1
    response=client.post(f'/api/events/{TOKEN}/photos',data={'uploader_name':'Deniz'},files=[('files',('new.jpg',image_bytes((200,200)),'image/jpeg')),('files',('bad.jpg',b'invalid','image/jpeg'))])
    assert response.status_code==400
    assert len(client.get(f'/api/admin/events/{TOKEN}/photos',headers=admin_headers).json())==1


def test_album_ownership_and_size_limit(client,admin_headers,monkeypatch):
    other=client.post('/api/admin/register',json={'email':'other@test.com','password':'OtherPassword123!'}).json()
    other_headers={'Authorization':f'Bearer {other["access_token"]}'}
    assert client.get(f'/api/admin/events/{TOKEN}/album.zip',headers=other_headers).status_code==404
    upload(client,image_bytes())
    from app.db import database
    from app.db.models import Photo
    with database.SessionLocal() as db:
        photo=db.query(Photo).one();photo.size=201*1024*1024;db.commit()
    assert client.get(f'/api/admin/events/{TOKEN}/album.zip',headers=admin_headers).status_code==413


def test_archive_storage_failure_returns_no_partial_zip(client,admin_headers,monkeypatch):
    upload(client,image_bytes())
    from app.services.photo_service import PhotoService
    def fail(*args,**kwargs):raise FileNotFoundError('missing')
    monkeypatch.setattr(PhotoService,'stream_photo',fail)
    assert client.get(f'/api/admin/events/{TOKEN}/album.zip',headers=admin_headers).status_code==503


def test_storage_failure_cleans_partial_upload(client,admin_headers,monkeypatch):
    from app.services.storage import LocalPrivateStorage
    from app.core.config import get_settings
    original=LocalPrivateStorage.put_bytes
    def fail_thumbnail(self,key,data,content_type):
        if '/thumb/' in key:raise OSError('write failed')
        return original(self,key,data,content_type)
    monkeypatch.setattr(LocalPrivateStorage,'put_bytes',fail_thumbnail)
    assert upload(client,image_bytes()).status_code==500
    assert client.get(f'/api/admin/events/{TOKEN}/photos',headers=admin_headers).json()==[]
    from pathlib import Path
    assert not list(Path(get_settings().local_storage_path).rglob('*.jpg'))
