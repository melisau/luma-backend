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
            if event and not event.album_public:
                raise HTTPException(status_code=404,detail='Fotoğraf bulunamadı.')
    if not event or not event.is_active or not event.access_code_hash:return
    raw=request.cookies.get(cookie_name(event),'')
    try:
        expires,digest=raw.split('.',1)
        valid=int(expires)>int(time.time()) and hmac.compare_digest(signature(event,expires),digest)
    except (ValueError,TypeError):valid=False
    if not valid:
        raise HTTPException(status_code=423,detail='Bu davetiye için erişim kodu gerekiyor.')


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
    event=get_admin_event_or_404(db,event_token,admin.id)
    expires=str(int(time.time())+TTL)
    response.set_cookie(cookie_name(event),f'{expires}.{signature(event,expires)}',max_age=TTL,httponly=True,secure=request.url.scheme=='https',samesite='lax',path='/api')
    response.headers['Cache-Control']='no-store'
    return {'unlocked':True}
