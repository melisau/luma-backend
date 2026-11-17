import hashlib
import hmac
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.database import get_db
from app.db.models import Event, Photo
from app.services import guest_access
from app.services.rate_limit import RateLimiter

router=APIRouter()
access_limiter=RateLimiter()
TTL=12*60*60


def cookie_name(event):
    return 'luma_access_'+hashlib.sha256(event.id.encode()).hexdigest()[:16]


def signature(event, expires):
    message=f'{event.id}:{event.access_code_hash}:{expires}'
    return hmac.new(get_settings().secret_key.encode(),message.encode(),hashlib.sha256).hexdigest()


def require_event_access(request: Request, db: Session=Depends(get_db)):
    """Runs before every public API request, often while a photo is still being uploaded over slow
    venue Wi-Fi. Hand the connection back as soon as the check is done: a held connection per
    in-flight upload exhausted the pool under load (150 guests) and every page timed out. The
    request's session reconnects by itself if the endpoint queries again."""
    try:
        _check_event_access(request, db)
    finally:
        db.close()


def _check_event_access(request: Request, db: Session):
    path=request.url.path
    event=None
    if path.startswith('/api/events/'):
        token=request.path_params.get('event_token')
        if token:
            event=db.query(Event).filter(Event.private_token==token).one_or_none()
    elif path.startswith('/api/photos/'):
        # Existing photo endpoints independently validate the administrator and ownership.
        if request.headers.get('authorization','').startswith('Bearer '):return
        photo_id=request.path_params.get('photo_id')
        if photo_id:
            event=db.query(Event).join(Photo).filter(Photo.id==photo_id).one_or_none()
            if event and not event.album_public and not slideshow_photo_visible(request,db,event,photo_id):
                raise HTTPException(status_code=404,detail='Fotoğraf bulunamadı.')
    from app.services.rate_limit import owner_can_reach_guests
    if event and not owner_can_reach_guests(event):
        raise HTTPException(status_code=403,detail='Bu davetiye henüz yayında değil.')
    from app.services.memory_retention import memories_expired
    if event and memories_expired(event) and (path.startswith('/api/photos/') or path.rstrip('/').endswith(('/photos','/messages'))):
        raise HTTPException(status_code=410,detail='Bu etkinliğin anı saklama süresi doldu.')
    if event and event.is_active and guest_access.is_personal(event):
        if _personal_access(request, db, event, path):
            return  # the personal link is stronger than the shared access code
    if not event or not event.is_active or not event.access_code_hash:return
    raw=request.cookies.get(cookie_name(event),'')
    try:
        expires,digest=raw.split('.',1)
        valid=int(expires)>int(time.time()) and hmac.compare_digest(signature(event,expires),digest)
    except (ValueError,TypeError):valid=False
    if not valid:
        raise HTTPException(status_code=423,detail='Bu davetiye için erişim kodu gerekiyor.')


# Requests a venue QR (upload key) may make: see the invitation, send photos. Not the album, the
# guestbook or RSVPs.
_UPLOAD_KEY_GET = ("", "invitation", "cover", "memory-cover", "music")


def _personal_access(request: Request, db: Session, event: Event, path: str) -> bool:
    """True when the request may go on; raises 401 otherwise."""
    rest = path.split(f"/api/events/{event.private_token}", 1)[1].strip("/") if path.startswith("/api/events/") else None
    if rest in ("guest-session", "upload-session", "unlock") and request.method == "POST":
        return True
    if _owner_preview_valid(request, event):
        return True
    guest = guest_access.device_guest(db, event, request)
    if guest:
        request.state.luma_guest_id = guest.id
        return True
    if rest is not None and (guest_access.upload_key_valid(event, request.headers.get("x-upload-key"))
                             or _upload_cookie_valid(request, event)):
        allowed = (request.method == "GET" and (rest in _UPLOAD_KEY_GET or rest.startswith("visual-assets/"))) or (
            request.method == "POST" and rest == "photos")
        if allowed:
            request.state.luma_upload_key = True
            return True
    raise guest_access.personal_link_required()


def upload_cookie_name(event):
    return 'luma_upload_'+hashlib.sha256(event.id.encode()).hexdigest()[:16]


def upload_signature(event, expires):
    # Includes the key, so renewing the key in the panel ends every QR session at once.
    return hmac.new(get_settings().secret_key.encode(),f'upload:{event.id}:{event.upload_key}:{expires}'.encode(),hashlib.sha256).hexdigest()


def _upload_cookie_valid(request: Request, event: Event) -> bool:
    if not guest_access.upload_key_valid(event, event.upload_key):  # outside the event days
        return False
    raw=request.cookies.get(upload_cookie_name(event),'')
    try:
        expires,digest=raw.split('.',1)
        return int(expires)>int(time.time()) and hmac.compare_digest(upload_signature(event,expires),digest)
    except (ValueError,TypeError):
        return False


def preview_cookie_name(event):
    return 'luma_preview_'+hashlib.sha256(event.id.encode()).hexdigest()[:16]


def preview_signature(event, expires):
    return hmac.new(get_settings().secret_key.encode(),f'preview:{event.id}:{expires}'.encode(),hashlib.sha256).hexdigest()


def _owner_preview_valid(request: Request, event: Event) -> bool:
    raw=request.cookies.get(preview_cookie_name(event),'')
    try:
        expires,digest=raw.split('.',1)
        return int(expires)>int(time.time()) and hmac.compare_digest(preview_signature(event,expires),digest)
    except (ValueError,TypeError):
        return False


def slideshow_photo_visible(request: Request, db: Session, event: Event, photo_id: str) -> bool:
    """A photo in the slide show is visible on the owner's screen (panel preview cookie), e.g. the
    venue screen, even when the album is not shared with guests."""
    from app.services import slideshow
    if not (_owner_preview_valid(request, event) or slideshow.guests_can_watch(event)):
        return False
    return slideshow.contains(db, event, photo_id)


class UnlockInput(BaseModel):
    code: str=Field(min_length=1,max_length=64)


@router.post('/events/{event_token}/unlock')
def unlock(event_token: str,payload: UnlockInput,request: Request,response: Response,db: Session=Depends(get_db)):
    access_limiter.check(f'{request.client.host if request.client else "unknown"}:{event_token}',5,detail='Çok fazla kod denemesi. Bir dakika sonra tekrar deneyin.')
    event=db.query(Event).filter(Event.private_token==event_token,Event.is_active.is_(True)).one_or_none()
    if not event:raise HTTPException(status_code=404,detail='Davetiye bulunamadı.')
    if event.access_code_hash and (len(payload.code.encode())>72 or not verify_password(payload.code,event.access_code_hash)):
        raise HTTPException(status_code=403,detail='Erişim kodu hatalı.')
    expires=str(int(time.time())+TTL)
    response.set_cookie(cookie_name(event),f'{expires}.{signature(event,expires)}',max_age=TTL,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/api')
    response.headers['Cache-Control']='no-store'
    return {'unlocked':True}


@router.post('/admin/events/{event_token}/access-preview')
def grant_owner_preview(event_token: str,request: Request,response: Response,db: Session=Depends(get_db)):
    from app.api.photos import _resolve_admin
    from app.services.event_service import get_admin_event_or_404
    admin=_resolve_admin(request.headers.get('authorization',''),db)
    event=get_admin_event_or_404(db,event_token,admin.id,write=False)
    expires=str(int(time.time())+TTL)
    response.set_cookie(cookie_name(event),f'{expires}.{signature(event,expires)}',max_age=TTL,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/api')
    # Lets the owner and their team see a personal-link invitation as guests do.
    response.set_cookie(preview_cookie_name(event),f'{expires}.{preview_signature(event,expires)}',max_age=TTL,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/api')
    response.headers['Cache-Control']='no-store'
    return {'unlocked':True}


class GuestSessionInput(BaseModel):
    guest_id: str=Field(min_length=1,max_length=36)
    token: str=Field(min_length=1,max_length=64)
    code: str|None=Field(default=None,max_length=12)


def _guest_summary(guest):
    return {'id':guest.id,'name':guest.name,'email':guest.email,'people':guest.people,'status':guest.status}


@router.post('/events/{event_token}/guest-session')
def guest_session(event_token: str,payload: GuestSessionInput,request: Request,response: Response,db: Session=Depends(get_db)):
    """Opens a personal invitation link on this device (see app/services/guest_access.py)."""
    from fastapi.responses import JSONResponse
    access_limiter.check(f'guest:{request.client.host if request.client else "unknown"}:{event_token}',20,detail='Çok fazla deneme. Bir dakika sonra tekrar deneyin.')
    response.headers['Cache-Control']='no-store'
    event=db.query(Event).filter(Event.private_token==event_token,Event.is_active.is_(True)).one_or_none()
    if not event:raise HTTPException(status_code=404,detail='Davetiye bulunamadı.')
    if not guest_access.is_personal(event):
        return {'mode':'open'}
    current=guest_access.device_guest(db,event,request)
    if current and current.id==payload.guest_id:
        return {'mode':'personal','guest':_guest_summary(current)}
    guest=guest_access.guest_from_link(db,event,payload.guest_id,payload.token)
    if not guest:
        raise HTTPException(status_code=403,detail='Bu bağlantı geçersiz ya da yenilenmiş. Etkinlik sahibinden yeni bağlantı isteyin.')
    from app.db.models import GuestDevice
    devices=db.query(GuestDevice).filter(GuestDevice.guest_id==guest.id).count()
    if devices<guest_access.device_allowance(guest) or (payload.code and guest_access.check_code(db,guest,payload.code)):
        guest_access.bind_device(db,guest,request,response,event)
        return {'mode':'personal','guest':_guest_summary(guest)}
    if payload.code:
        detail='Kod hatalı veya süresi dolmuş. Yeni kod için tekrar deneyin.'
    else:
        guest_access.send_code(db,event,guest)
        detail='Bu davetiye başka bir cihazda zaten açıldı. Devam etmek için e-postanıza gönderdiğimiz kodu girin.'
    return JSONResponse(status_code=403,content={'detail':detail,'code_required':True,'email_hint':guest_access.email_hint(guest.email)},headers={'Cache-Control':'no-store'})



class UploadSessionInput(BaseModel):
    key: str=Field(min_length=1,max_length=64)


@router.post('/events/{event_token}/upload-session')
def upload_session(event_token: str,payload: UploadSessionInput,request: Request,response: Response,db: Session=Depends(get_db)):
    """Venue QR (personal-link events): turns the upload key into a cookie, so the upload page and its
    images load without the key on every request. Upload only, on the event days."""
    access_limiter.check(f'upload:{request.client.host if request.client else "unknown"}:{event_token}',30,detail='Çok fazla deneme. Bir dakika sonra tekrar deneyin.')
    response.headers['Cache-Control']='no-store'
    event=db.query(Event).filter(Event.private_token==event_token,Event.is_active.is_(True)).one_or_none()
    if not event:raise HTTPException(status_code=404,detail='Davetiye bulunamadı.')
    if not guest_access.is_personal(event):
        return {'mode':'open'}
    if not guest_access.upload_key_valid(event,payload.key):
        raise HTTPException(status_code=403,detail='Bu QR kod şu anda geçerli değil. Fotoğraf yükleme etkinlik günlerinde açıktır.')
    expires=str(int(time.time())+24*60*60)
    response.set_cookie(upload_cookie_name(event),f'{expires}.{upload_signature(event,expires)}',max_age=24*60*60,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/api')
    return {'mode':'upload'}
