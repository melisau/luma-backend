"""Create the first production administrator with a one-time random password."""
import secrets
import sys

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.database import SessionLocal, init_db
from app.db.models import AdminUser


def main() -> int:
    settings = get_settings()
    if settings.environment != "production":
        print("Bu komut yalnızca ENVIRONMENT=production iken çalışır.", file=sys.stderr)
        return 2
    if settings.bootstrap_admin_enabled:
        print("BOOTSTRAP_ADMIN_ENABLED üretimde false olmalı.", file=sys.stderr)
        return 2

    try:
        settings.validate_production()
        init_db()
    except Exception as error:
        print(f"Üretim yapılandırması veya veritabanı hazır değil: {error}", file=sys.stderr)
        return 2

    email = input("İlk yönetici e-posta adresi: ").strip().lower()
    if not email or "@" not in email:
        print("Geçerli bir e-posta adresi gerekli.", file=sys.stderr)
        return 2

    password = secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        if db.query(AdminUser.id).first():
            print("Yönetici hesabı zaten var; mevcut hesaplara dokunulmadı.", file=sys.stderr)
            return 1
        db.add(AdminUser(email=email, password_hash=hash_password(password)))
        db.commit()
    except IntegrityError:
        db.rollback()
        print("Yönetici hesabı eşzamanlı olarak oluşturulmuş; hiçbir parola yazdırılmadı.", file=sys.stderr)
        return 1
    finally:
        db.close()

    print("İlk yönetici oluşturuldu. Bu parolayı şimdi güvenli bir parola kasasına kaydedin:")
    print(f"E-posta: {email}")
    print(f"Tek seferlik parola: {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
