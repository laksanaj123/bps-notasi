"""Migrasi sekali-jalan: gabungkan tabel `pegawai` (direktori tanpa login)
ke tabel `users` (setiap pegawai jadi User berrole pegawai), dan perbarui
seluruh referensi (Meeting.pimpinan_id/notulis_id/peserta_ids,
MeetingPeserta.user_id) supaya mengarah ke users.id.

Jalankan MANUAL sebelum menjalankan versi backend yang baru:

    cd backend
    python -m scripts.migrate_pegawai_to_user

Aman dijalankan berulang kali (idempoten - mengecek sebelum menyisipkan/
mengubah data). Membuat backup notasi.db sebelum mengubah apapun.
"""
import json
import re
import secrets
import shutil
import string
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text  # noqa: E402

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.config import settings, BASE_DIR  # noqa: E402


def _ensure_columns():
    """Sama seperti main.py._auto_migrate() - dijalankan mandiri di sini
    supaya skrip ini tidak perlu mengimpor seluruh main.py (yang memuat
    modul ML berat seperti whisper/ctranslate2)."""
    needed = {
        "users": {
            "jabatan": "TEXT",
            "urutan": "INTEGER DEFAULT 0",
            "must_reset_password": "INTEGER DEFAULT 0",
        },
        "meeting_peserta": {
            "user_id": "INTEGER",
        },
    }
    with engine.connect() as conn:
        for table, cols in needed.items():
            rows = conn.execute(sa_text(f"PRAGMA table_info({table})")).fetchall()
            if not rows:
                continue
            existing = {r[1] for r in rows}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                    print(f"[migrate] kolom '{col}' ditambahkan ke tabel {table}.")
        conn.commit()


def _remap_legacy_notulis_role():
    """Harus dijalankan lewat SQL mentah SEBELUM query ORM apapun pada User -
    RoleEnum di models.py sudah tidak punya nilai 'notulis', jadi baris User
    dengan role='notulis' akan gagal di-deserialize ORM kalau belum diremap."""
    with engine.connect() as conn:
        result = conn.execute(sa_text("UPDATE users SET role='pegawai' WHERE role='notulis'"))
        conn.commit()
        if result.rowcount:
            print(f"[migrate] {result.rowcount} akun role 'notulis' diubah jadi 'pegawai'.")


def _slugify(nama: str) -> str:
    base = re.sub(r"[^a-z0-9]+", ".", nama.lower()).strip(".")
    return base or "pengguna"


def _random_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    db_path_str = settings.DATABASE_URL.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path_str
    if db_path.exists():
        backup_path = db_path.with_name(f"{db_path.name}.bak-before-user-merge-{datetime.now():%Y%m%d%H%M%S}")
        shutil.copy2(db_path, backup_path)
        print(f"[migrate] Backup dibuat: {backup_path}")
    else:
        print(f"[migrate] PERINGATAN: file database {db_path} tidak ditemukan, lanjut (mungkin baru).")

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _remap_legacy_notulis_role()

    db = SessionLocal()
    try:
        pegawai_rows = db.query(models.Pegawai).order_by(models.Pegawai.urutan).all()
        print(f"[migrate] {len(pegawai_rows)} baris pegawai (tabel lama) ditemukan.")
        if not pegawai_rows:
            print("[migrate] Tidak ada yang perlu dimigrasi. Selesai.")
            return

        users_by_name = {u.nama.strip().lower(): u for u in db.query(models.User).all()}
        existing_usernames = {u.username for u in db.query(models.User.username).all()}

        id_map = {}   # pegawai.id (lama) -> users.id (baru)
        created, reused = 0, 0
        credentials_report = []

        for peg in pegawai_rows:
            key = peg.nama.strip().lower()
            user = users_by_name.get(key)
            if user:
                if not user.jabatan:
                    user.jabatan = peg.jabatan
                if not user.urutan:
                    user.urutan = peg.urutan
                reused += 1
            else:
                base_username = _slugify(peg.nama)
                username = base_username
                n = 1
                while username in existing_usernames:
                    n += 1
                    username = f"{base_username}{n}"
                existing_usernames.add(username)
                temp_password = _random_password()
                user = models.User(
                    nama=peg.nama, username=username, email=None,
                    password_hash=hash_password(temp_password),
                    role=models.RoleEnum.pegawai, is_active=True,
                    jabatan=peg.jabatan, urutan=peg.urutan,
                    must_reset_password=True,
                )
                db.add(user)
                db.flush()   # supaya user.id langsung terisi
                users_by_name[key] = user
                credentials_report.append((peg.nama, username, temp_password))
                created += 1
            id_map[peg.id] = user.id

        db.commit()
        print(f"[migrate] {created} akun pegawai baru dibuat, {reused} dicocokkan ke akun User yang sudah ada.")

        # --- repoint FK: Meeting.pimpinan_id / notulis_id / peserta_ids (JSON) ---
        meetings = db.query(models.Meeting).all()
        n_pimpinan = n_notulis = n_peserta_ids = 0
        for m in meetings:
            if m.pimpinan_id in id_map:
                m.pimpinan_id = id_map[m.pimpinan_id]
                n_pimpinan += 1
            if m.notulis_id in id_map:
                m.notulis_id = id_map[m.notulis_id]
                n_notulis += 1
            if m.peserta_ids:
                try:
                    old_ids = json.loads(m.peserta_ids)
                    new_ids = [id_map.get(i, i) for i in old_ids]
                    if new_ids != old_ids:
                        m.peserta_ids = json.dumps(new_ids)
                        n_peserta_ids += 1
                except (ValueError, TypeError):
                    pass

        # --- repoint FK: MeetingPeserta.user_id (dulu pegawai_id, kolom lama
        # dibaca lewat SQL mentah karena sudah tidak ada di model ORM) ---
        n_mp = 0
        old_pegawai_id_rows = db.execute(
            sa_text("SELECT id, pegawai_id FROM meeting_peserta WHERE pegawai_id IS NOT NULL")
        ).fetchall()
        for row_id, old_pegawai_id in old_pegawai_id_rows:
            if old_pegawai_id in id_map:
                db.execute(
                    sa_text("UPDATE meeting_peserta SET user_id = :uid WHERE id = :rid AND user_id IS NULL"),
                    {"uid": id_map[old_pegawai_id], "rid": row_id},
                )
                n_mp += 1

        db.commit()
        print(f"[migrate] FK diperbarui -> pimpinan:{n_pimpinan} notulis:{n_notulis} "
              f"peserta_ids:{n_peserta_ids} meeting_peserta:{n_mp}")

        if credentials_report:
            report_path = BASE_DIR / f"migrasi_kredensial_{datetime.now():%Y%m%d%H%M%S}.txt"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("Nama\tUsername\tPassword Sementara\n")
                for nama, username, pw in credentials_report:
                    f.write(f"{nama}\t{username}\t{pw}\n")
            print(f"[migrate] Kredensial {len(credentials_report)} akun baru disimpan di: {report_path}")
            print("[migrate] PENTING: bagikan file ini secara aman ke masing-masing pegawai lalu hapus dari server.")
            print("[migrate] Setiap akun baru wajib ganti password saat login pertama (must_reset_password=True).")

        print("[migrate] Selesai.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
