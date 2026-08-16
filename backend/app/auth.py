"""
Autentikasi: hashing kata sandi (bcrypt langsung, TANPA passlib) dan JWT.

Catatan penting: versi sebelumnya memakai passlib, yang TIDAK kompatibel
dengan bcrypt >= 4.1 (error "module 'bcrypt' has no attribute '__about__'").
Kode ini memanggil bcrypt secara langsung sehingga bekerja dengan semua
versi bcrypt 4.x dan 5.x tanpa perlu pin versi khusus.
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesi tidak valid atau telah kedaluwarsa, silakan login kembali",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or user.is_active is False:
        raise credentials_exception
    return user


def require_roles(*roles: str):
    """Dependency factory: 403 bila role pengguna saat ini bukan salah satu dari `roles`.
    Contoh: current_user: models.User = Depends(require_roles("admin"))."""
    def checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki hak akses untuk aksi ini",
            )
        return current_user
    return checker


def can_write_meeting(user: models.User, meeting: models.Meeting) -> bool:
    """Hanya ada 2 role permanen (admin/pegawai) - "menjadi notulis" bukan
    role, melainkan penugasan per-rapat: siapapun (admin atau pegawai) yang
    ditunjuk sebagai notulis_id rapat ini punya hak tulis penuh atas rapat
    tsb. Admin selalu punya hak tulis di semua rapat."""
    if user.role == models.RoleEnum.admin:
        return True
    return meeting.notulis_id is not None and meeting.notulis_id == user.id


def assert_can_write_meeting(user: models.User, meeting: models.Meeting) -> None:
    if not can_write_meeting(user, meeting):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda bukan notulis rapat ini - hanya notulis rapat atau admin yang dapat mengubahnya",
        )
