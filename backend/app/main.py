import json
import threading
import uuid
from datetime import date
from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .auth import authenticate_user, create_access_token, get_current_user, hash_password
from .data.pegawai_seed import PEGAWAI_SEED
from .services.transcription import transcribe_audio, preload_stt_model, reset_local_model
from .services.document_extract import extract_text, UnsupportedMaterialError
from .services.summarizer import summarize_transcript
from .services.docx_export import build_notulensi_docx
from .services.pdf_export import convert_docx_to_pdf, find_soffice

Base.metadata.create_all(bind=engine)


def _auto_migrate():
    """Menambahkan kolom yang belum ada pada database lama (SQLite ALTER TABLE).

    SQLAlchemy create_all TIDAK mengubah tabel yang sudah ada, sehingga database
    dari versi aplikasi sebelumnya akan kekurangan kolom baru dan menyebabkan
    error 'no such column' saat proses/export. Fungsi ini memperbaikinya
    otomatis tanpa menghapus data."""
    needed = {
        "unit_kerja": "TEXT",
        "waktu_mulai": "TEXT",
        "waktu_selesai": "TEXT",
        "pimpinan_id": "INTEGER",
        "notulis_id": "INTEGER",
        "peserta_ids": "TEXT DEFAULT '[]'",
        "progress": "INTEGER DEFAULT 0",
        "progress_stage": "TEXT DEFAULT ''",
        "catatan_notulis": "TEXT",
    }
    with engine.connect() as conn:
        rows = conn.execute(sa_text("PRAGMA table_info(meetings)")).fetchall()
        if not rows:
            return  # tabel belum ada; create_all sudah membuatnya dengan skema baru
        existing = {r[1] for r in rows}
        for col, ddl in needed.items():
            if col not in existing:
                conn.execute(sa_text(f"ALTER TABLE meetings ADD COLUMN {col} {ddl}"))
                print(f"[NOTASI] Migrasi: kolom '{col}' ditambahkan ke tabel meetings.")
        conn.commit()


_auto_migrate()


def _load_settings_overrides():
    """Baca override provider AI tersimpan (halaman Pengaturan) dan terapkan
    ke singleton `settings` di memori, supaya berlaku persis seperti setelan
    .env - tapi bisa diubah dari UI tanpa restart server. Dipanggil sekali
    saat start; PATCH /api/settings juga langsung menerapkan ke `settings`
    sehingga tidak perlu restart untuk perubahan berikutnya."""
    db = SessionLocal()
    try:
        row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        if not row:
            return
        for field in ("stt_provider", "llm_provider", "openai_api_key",
                      "ollama_model", "whisper_local_model"):
            value = getattr(row, field)
            if value:
                setattr(settings, field.upper(), value)
    finally:
        db.close()


_load_settings_overrides()

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # batasi ke domain internal instansi saat produksi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def seed_data():
    db = next(get_db())

    if not db.query(models.User).filter(models.User.username == settings.DEFAULT_ADMIN_USERNAME).first():
        db.add(models.User(
            nama=settings.DEFAULT_ADMIN_NAME,
            username=settings.DEFAULT_ADMIN_USERNAME,
            email="admin@notasi.local",
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role=models.RoleEnum.admin,
        ))
        db.commit()
        print(f"[NOTASI] Akun default -> {settings.DEFAULT_ADMIN_USERNAME} / {settings.DEFAULT_ADMIN_PASSWORD}")

    if db.query(models.Pegawai).count() == 0:
        for i, (nama, jabatan) in enumerate(PEGAWAI_SEED):
            db.add(models.Pegawai(nama=nama, jabatan=jabatan, urutan=i))
        db.commit()
        print(f"[NOTASI] {len(PEGAWAI_SEED)} data pegawai berhasil dimuat.")

    # Rapat yang terhenti di status 'diproses' karena server dimatikan -> tandai gagal
    stale = db.query(models.Meeting).filter(models.Meeting.status == models.StatusEnum.diproses).all()
    for m in stale:
        m.status = models.StatusEnum.gagal
        m.progress_stage = "Terputus karena server dimulai ulang. Silakan proses ulang."
    if stale:
        db.commit()
        print(f"[NOTASI] {len(stale)} proses yang terputus ditandai gagal.")

    print(f"[NOTASI] STT_PROVIDER={settings.STT_PROVIDER} | LLM_PROVIDER={settings.LLM_PROVIDER}")
    if settings.STT_PROVIDER == "local":
        print(f"[NOTASI] Whisper: model={settings.WHISPER_LOCAL_MODEL} "
              f"device={settings.WHISPER_LOCAL_DEVICE} beam={settings.WHISPER_BEAM_SIZE} "
              f"vad={settings.WHISPER_VAD} batch={settings.WHISPER_BATCH_SIZE}")
        # dimuat di latar belakang agar server langsung siap menerima request
        threading.Thread(target=preload_stt_model, daemon=True).start()
    if settings.DEMO_MODE:
        print("[NOTASI] MODE DEMO penuh (STT & LLM memakai data contoh).")


def _get_kepala_bps(db: Session):
    return db.query(models.Pegawai).filter(models.Pegawai.jabatan.ilike("%Kepala BPS%")).first()


# ============================================================
#  INFO PUBLIK
# ============================================================
@app.get("/api/config")
def public_config():
    return {
        "app_name": settings.APP_NAME,
        "demo_mode": settings.DEMO_MODE,
        "stt_provider": settings.STT_PROVIDER,
        "llm_provider": settings.LLM_PROVIDER,
        "pdf_ready": find_soffice() is not None,
        "whisper_model": settings.WHISPER_LOCAL_MODEL if settings.STT_PROVIDER == "local" else None,
        "whisper_device": settings.WHISPER_LOCAL_DEVICE if settings.STT_PROVIDER == "local" else None,
        "nama_instansi": settings.NAMA_INSTANSI,
        "alamat_instansi": settings.ALAMAT_INSTANSI,
        "unit_kerja_default": settings.UNIT_KERJA_DEFAULT,
    }


# ============================================================
#  PENGATURAN MODE AI (admin-only) - lihat _load_settings_overrides()
# ============================================================
VALID_STT_PROVIDERS = {"demo", "openai", "local"}
VALID_LLM_PROVIDERS = {"demo", "openai", "ollama"}


def _mask_key(key: str) -> str:
    if not key or len(key) < 4:
        return "****"
    return "*" * 8 + key[-4:]


@app.get("/api/settings", response_model=schemas.AppSettingsOut)
def get_ai_settings(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat melihat pengaturan mode AI")
    return schemas.AppSettingsOut(
        stt_provider=settings.STT_PROVIDER,
        llm_provider=settings.LLM_PROVIDER,
        ollama_model=settings.OLLAMA_MODEL,
        whisper_local_model=settings.WHISPER_LOCAL_MODEL,
        openai_api_key_set=bool(settings.OPENAI_API_KEY),
        openai_api_key_masked=_mask_key(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None,
    )


@app.patch("/api/settings", response_model=schemas.AppSettingsOut)
def update_ai_settings(payload: schemas.AppSettingsUpdate, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat mengubah pengaturan mode AI")

    data = payload.model_dump(exclude_unset=True)
    if "stt_provider" in data and data["stt_provider"] not in VALID_STT_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"stt_provider harus salah satu dari {VALID_STT_PROVIDERS}")
    if "llm_provider" in data and data["llm_provider"] not in VALID_LLM_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"llm_provider harus salah satu dari {VALID_LLM_PROVIDERS}")

    # Validasi: provider openai butuh API key (baik dari payload ini maupun yang sudah tersimpan)
    new_openai_key = data.get("openai_api_key", None) or settings.OPENAI_API_KEY
    wants_openai = data.get("stt_provider") == "openai" or data.get("llm_provider") == "openai"
    if wants_openai and not new_openai_key:
        raise HTTPException(status_code=400,
                             detail="Provider 'openai' butuh OPENAI_API_KEY - isi dulu API key-nya")

    row = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if not row:
        row = models.AppSettings(id=1)
        db.add(row)

    whisper_changed = False
    for field, value in data.items():
        if value in (None, ""):
            continue
        setattr(row, field, value)
        setattr(settings, field.upper(), value)
        if field in ("whisper_local_model", "stt_provider"):
            whisper_changed = True
    db.commit()

    if whisper_changed:
        reset_local_model()

    return schemas.AppSettingsOut(
        stt_provider=settings.STT_PROVIDER,
        llm_provider=settings.LLM_PROVIDER,
        ollama_model=settings.OLLAMA_MODEL,
        whisper_local_model=settings.WHISPER_LOCAL_MODEL,
        openai_api_key_set=bool(settings.OPENAI_API_KEY),
        openai_api_key_masked=_mask_key(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None,
    )


# ============================================================
#  AUTH
# ============================================================
@app.post("/api/auth/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username atau kata sandi salah")
    token = create_access_token({"sub": user.username, "role": user.role.value})
    return schemas.Token(access_token=token)


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/api/auth/register", response_model=schemas.UserOut)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db),
             current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat menambah pengguna")
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username sudah digunakan")
    user = models.User(
        nama=payload.nama, username=payload.username, email=payload.email,
        password_hash=hash_password(payload.password), role=models.RoleEnum(payload.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================
#  PEGAWAI
# ============================================================
@app.get("/api/pegawai", response_model=List[schemas.PegawaiOut])
def list_pegawai(db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    return db.query(models.Pegawai).order_by(models.Pegawai.urutan).all()


# ============================================================
#  MEETINGS - Create + Upload
# ============================================================
def _save_upload(file: UploadFile, dest_dir: Path, max_mb: int) -> Path:
    ext = Path(file.filename).suffix or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = dest_dir / fname
    max_bytes = max_mb * 1024 * 1024
    total = 0
    with open(dest, "wb") as buf:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                buf.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Ukuran berkas melebihi batas maksimum {max_mb} MB")
            buf.write(chunk)
    return dest


@app.post("/api/meetings", response_model=schemas.MeetingOut)
def create_meeting(
    judul_rapat: str = Form(...),
    tanggal: str = Form(...),
    waktu_mulai: str = Form(""),
    waktu_selesai: str = Form(""),
    unit_kerja: str = Form(""),
    lokasi: str = Form(""),
    agenda: str = Form(""),
    catatan_notulis: str = Form(""),
    pimpinan_id: int = Form(...),
    notulis_id: int = Form(...),
    peserta_ids: str = Form("[]"),
    audio: UploadFile = File(...),
    materi_files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        peserta_id_list = json.loads(peserta_ids)
        assert isinstance(peserta_id_list, list)
    except (json.JSONDecodeError, AssertionError):
        raise HTTPException(status_code=400, detail="Format peserta_ids tidak valid")

    saved_path = _save_upload(audio, settings.UPLOAD_DIR, settings.MAX_UPLOAD_MB)
    meeting = models.Meeting(
        unit_kerja=unit_kerja or settings.UNIT_KERJA_DEFAULT,
        judul_rapat=judul_rapat, tanggal=tanggal,
        waktu_mulai=waktu_mulai, waktu_selesai=waktu_selesai,
        lokasi=lokasi, agenda=agenda, catatan_notulis=catatan_notulis,
        pimpinan_id=pimpinan_id, notulis_id=notulis_id,
        peserta_ids=json.dumps(peserta_id_list),
        file_audio=str(saved_path.relative_to(settings.UPLOAD_DIR)),
        status=models.StatusEnum.menunggu, progress=0, progress_stage="",
        user_id=current_user.id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    for f in materi_files:
        if not f.filename:
            continue
        materi_path = _save_upload(f, settings.MATERI_DIR, settings.MAX_MATERI_MB)
        try:
            teks = extract_text(materi_path)
        except UnsupportedMaterialError as e:
            materi_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"{f.filename}: {e}")
        db.add(models.MeetingMaterial(
            meeting_id=meeting.id,
            file_path=materi_path.name,
            nama_asli=f.filename,
            teks_terekstrak=teks,
        ))
    db.commit()

    return meeting


# ============================================================
#  PROSES AI - berjalan di BACKGROUND THREAD dengan progress 0-100
# ============================================================
def _set_progress(db: Session, meeting: models.Meeting, pct: int, stage: str):
    meeting.progress = pct
    meeting.progress_stage = stage
    db.commit()


def _run_ai_pipeline(meeting_id: int):
    """Worker background: STT -> LLM -> simpan. Memperbarui kolom progress
    secara berkala agar frontend dapat menampilkan lingkaran progres 0-100%."""
    db = SessionLocal()
    try:
        meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
        if not meeting:
            return

        _set_progress(db, meeting, 10, "Menyiapkan berkas")
        audio_path = settings.UPLOAD_DIR / meeting.file_audio

        if audio_path.suffix.lower() == ".txt":
            # Berkas yang diunggah sudah berupa teks transkrip -> STT dilewati sepenuhnya.
            _set_progress(db, meeting, 60, "Menggunakan teks transkrip yang diunggah")
            transcript_text = audio_path.read_text(encoding="utf-8", errors="ignore")
        else:
            _set_progress(db, meeting, 20, "Mengubah suara menjadi teks (speech-to-text)")

            def _stt_progress(fraction: float, stage: str):
                # Tahap STT memakai rentang progres 20-60%.
                _set_progress(db, meeting, 20 + int(40 * fraction), stage)

            transcript_text = transcribe_audio(audio_path, progress_cb=_stt_progress)
            _set_progress(db, meeting, 60, "Transkripsi selesai, menyiapkan analisis")
        peserta_nama = ", ".join(
            p.nama for p in db.query(models.Pegawai).filter(
                models.Pegawai.id.in_(json.loads(meeting.peserta_ids or "[]"))
            ).all()
        )
        pimpinan = db.query(models.Pegawai).filter(models.Pegawai.id == meeting.pimpinan_id).first()
        materi_list = db.query(models.MeetingMaterial).filter(
            models.MeetingMaterial.meeting_id == meeting.id
        ).all()
        materi_rapat = "\n\n".join(
            f"--- {m.nama_asli} ---\n{m.teks_terekstrak}" for m in materi_list if m.teks_terekstrak
        )

        _set_progress(db, meeting, 70, "Menyusun ringkasan, keputusan, dan tindak lanjut")
        result = summarize_transcript(transcript_text, {
            "judul_rapat": meeting.judul_rapat,
            "tanggal": meeting.tanggal,
            "pimpinan": pimpinan.nama if pimpinan else "",
            "peserta": peserta_nama,
            "agenda": meeting.agenda,
            "materi_rapat": materi_rapat,
            "catatan_notulis": meeting.catatan_notulis,
        })

        _set_progress(db, meeting, 90, "Menyimpan hasil ke basis data")
        db.add(models.Transcript(meeting_id=meeting.id, teks_transkripsi=transcript_text))
        db.add(models.Summary(
            meeting_id=meeting.id,
            ringkasan=json.dumps(result["ringkasan"], ensure_ascii=False),
            keputusan=json.dumps(result["keputusan"], ensure_ascii=False),
        ))
        for item in result["tindak_lanjut"]:
            db.add(models.ActionItem(
                meeting_id=meeting.id,
                deskripsi=item.get("deskripsi", ""),
                penanggung_jawab=item.get("penanggung_jawab", "Belum ditentukan"),
                deadline=item.get("deadline", "Belum ditentukan"),
                status=models.ActionStatusEnum.pending,
            ))

        meeting.status = models.StatusEnum.selesai
        meeting.progress = 100
        meeting.progress_stage = "Selesai"
        db.commit()
    except Exception as e:
        db.rollback()
        meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = models.StatusEnum.gagal
            meeting.progress_stage = f"Gagal: {e}"
            db.commit()
    finally:
        db.close()


@app.post("/api/meetings/{meeting_id}/process")
def process_meeting(meeting_id: int, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    """Memulai pipeline AI di background. Frontend memantau kemajuan lewat
    GET /api/meetings/{id}/progress. Pemrosesan tidak lagi memblokir request
    sehingga pengguna bebas berpindah halaman selama proses berjalan."""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    if meeting.status == models.StatusEnum.diproses:
        raise HTTPException(status_code=400, detail="Rapat ini sedang diproses")

    # bersihkan hasil lama bila proses ulang (mis. setelah gagal)
    db.query(models.Transcript).filter(models.Transcript.meeting_id == meeting_id).delete()
    db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).delete()
    db.query(models.ActionItem).filter(models.ActionItem.meeting_id == meeting_id).delete()

    meeting.status = models.StatusEnum.diproses
    meeting.progress = 5
    meeting.progress_stage = "Masuk antrean pemrosesan"
    db.commit()

    threading.Thread(target=_run_ai_pipeline, args=(meeting_id,), daemon=True).start()
    return {"id": meeting_id, "status": "diproses"}


@app.get("/api/meetings/{meeting_id}/progress", response_model=schemas.ProgressOut)
def meeting_progress(meeting_id: int, db: Session = Depends(get_db),
                      current_user: models.User = Depends(get_current_user)):
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    return schemas.ProgressOut(
        id=meeting.id, status=meeting.status.value,
        progress=meeting.progress or 0, progress_stage=meeting.progress_stage or "",
    )


# ============================================================
#  READ / UPDATE / DELETE
# ============================================================
def _to_detail(db: Session, meeting: models.Meeting) -> schemas.MeetingDetailOut:
    transcript = db.query(models.Transcript).filter(models.Transcript.meeting_id == meeting.id).first()
    summary = db.query(models.Summary).filter(models.Summary.meeting_id == meeting.id).first()
    actions = db.query(models.ActionItem).filter(models.ActionItem.meeting_id == meeting.id).all()
    docs = db.query(models.Documentation).filter(models.Documentation.meeting_id == meeting.id).all()
    materi = db.query(models.MeetingMaterial).filter(models.MeetingMaterial.meeting_id == meeting.id).all()

    pimpinan = db.query(models.Pegawai).filter(models.Pegawai.id == meeting.pimpinan_id).first()
    notulis = db.query(models.Pegawai).filter(models.Pegawai.id == meeting.notulis_id).first()
    peserta = db.query(models.Pegawai).filter(
        models.Pegawai.id.in_(json.loads(meeting.peserta_ids or "[]"))
    ).all()

    return schemas.MeetingDetailOut(
        id=meeting.id, unit_kerja=meeting.unit_kerja, judul_rapat=meeting.judul_rapat,
        tanggal=meeting.tanggal, waktu_mulai=meeting.waktu_mulai, waktu_selesai=meeting.waktu_selesai,
        lokasi=meeting.lokasi, agenda=meeting.agenda, catatan_notulis=meeting.catatan_notulis,
        status=meeting.status.value,
        progress=meeting.progress or 0, progress_stage=meeting.progress_stage or "",
        created_at=meeting.created_at,
        pimpinan=schemas.PegawaiOut.model_validate(pimpinan) if pimpinan else None,
        notulis=schemas.PegawaiOut.model_validate(notulis) if notulis else None,
        peserta=[schemas.PegawaiOut.model_validate(p) for p in peserta],
        transkripsi=transcript.teks_transkripsi if transcript else None,
        ringkasan=json.loads(summary.ringkasan) if summary else [],
        keputusan=json.loads(summary.keputusan) if summary else [],
        tindak_lanjut=[schemas.ActionItemOut.model_validate(a) for a in actions],
        dokumentasi=[
            schemas.DocumentationOut(
                id=d.id, file_path=d.file_path, keterangan=d.keterangan,
                url=f"/media/bukti/{d.file_path}",
            ) for d in docs
        ],
        materi=[
            schemas.MaterialOut(id=m.id, nama_asli=m.nama_asli, url=f"/media/materi/{m.file_path}")
            for m in materi
        ],
    )


@app.get("/api/meetings", response_model=List[schemas.MeetingOut])
def list_meetings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Meeting).order_by(models.Meeting.created_at.desc()).all()


@app.get("/api/meetings/{meeting_id}", response_model=schemas.MeetingDetailOut)
def get_meeting(meeting_id: int, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    return _to_detail(db, meeting)


@app.patch("/api/meetings/{meeting_id}", response_model=schemas.MeetingDetailOut)
def update_meeting(meeting_id: int, payload: schemas.MeetingUpdate,
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    """Update (CRUD): penyuntingan metadata rapat dari halaman Arsip."""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    data = payload.model_dump(exclude_unset=True)
    if "peserta_ids" in data and data["peserta_ids"] is not None:
        data["peserta_ids"] = json.dumps(data["peserta_ids"])
    for field, value in data.items():
        setattr(meeting, field, value)
    db.commit()
    return _to_detail(db, meeting)


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    """Delete (CRUD): menghapus rapat beserta seluruh berkas terkait."""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    if meeting.status == models.StatusEnum.diproses:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus rapat yang sedang diproses")

    # hapus berkas fisik: audio, foto bukti, hasil ekspor
    if meeting.file_audio:
        (settings.UPLOAD_DIR / meeting.file_audio).unlink(missing_ok=True)
    for d in db.query(models.Documentation).filter(models.Documentation.meeting_id == meeting_id).all():
        (settings.BUKTI_DIR / d.file_path).unlink(missing_ok=True)
    for m in db.query(models.MeetingMaterial).filter(models.MeetingMaterial.meeting_id == meeting_id).all():
        (settings.MATERI_DIR / m.file_path).unlink(missing_ok=True)
    for a in db.query(models.Archive).filter(models.Archive.meeting_id == meeting_id).all():
        (settings.EXPORT_DIR / a.file_docx).unlink(missing_ok=True)

    db.delete(meeting)   # cascade menghapus transcript/summary/action_items/archives/dokumentasi/materi
    db.commit()
    return {"ok": True}


@app.patch("/api/meetings/{meeting_id}/summary", response_model=schemas.MeetingDetailOut)
def update_summary(meeting_id: int, payload: schemas.SummaryUpdate, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    summary = db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).first()
    if not summary:
        raise HTTPException(status_code=400, detail="Rapat belum diproses AI")
    if payload.ringkasan is not None:
        summary.ringkasan = json.dumps(payload.ringkasan, ensure_ascii=False)
    if payload.keputusan is not None:
        summary.keputusan = json.dumps(payload.keputusan, ensure_ascii=False)
    db.commit()
    return _to_detail(db, meeting)


@app.put("/api/meetings/{meeting_id}/content", response_model=schemas.MeetingDetailOut)
def update_meeting_content(meeting_id: int, payload: schemas.MeetingContentUpdate,
                            db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_current_user)):
    """Simpan-semua dari halaman Editor: transkripsi, ringkasan, keputusan, dan
    seluruh baris tindak lanjut disunting sekaligus dalam satu permintaan."""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")

    # --- Transkripsi ---
    if payload.transkripsi is not None:
        row = db.query(models.Transcript).filter(models.Transcript.meeting_id == meeting_id).first()
        if row:
            row.teks_transkripsi = payload.transkripsi
        else:
            db.add(models.Transcript(meeting_id=meeting_id, teks_transkripsi=payload.transkripsi))

    # --- Ringkasan & keputusan ---
    if payload.ringkasan is not None or payload.keputusan is not None:
        summary = db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).first()
        if not summary:
            summary = models.Summary(meeting_id=meeting_id, ringkasan="[]", keputusan="[]")
            db.add(summary)
            db.flush()
        if payload.ringkasan is not None:
            summary.ringkasan = json.dumps(payload.ringkasan, ensure_ascii=False)
        if payload.keputusan is not None:
            summary.keputusan = json.dumps(payload.keputusan, ensure_ascii=False)

    # --- Tindak lanjut: ganti seluruh daftar dengan yang dikirim editor ---
    if payload.tindak_lanjut is not None:
        db.query(models.ActionItem).filter(models.ActionItem.meeting_id == meeting_id).delete()
        for item in payload.tindak_lanjut:
            if not (item.deskripsi or "").strip():
                continue
            try:
                st = models.ActionStatusEnum(item.status or "Pending")
            except ValueError:
                st = models.ActionStatusEnum.pending
            db.add(models.ActionItem(
                meeting_id=meeting_id,
                deskripsi=item.deskripsi.strip(),
                penanggung_jawab=(item.penanggung_jawab or "Belum ditentukan").strip(),
                deadline=(item.deadline or "Belum ditentukan").strip(),
                status=st,
            ))

    # rapat yang sebelumnya gagal/menunggu menjadi selesai bila kini sudah berisi
    if meeting.status != models.StatusEnum.diproses:
        has_summary = db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).first()
        if has_summary:
            meeting.status = models.StatusEnum.selesai
            meeting.progress = 100

    db.commit()
    return _to_detail(db, meeting)


@app.patch("/api/action-items/{item_id}", response_model=schemas.ActionItemOut)
def update_action_item(item_id: int, payload: schemas.ActionItemUpdate, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    item = db.query(models.ActionItem).filter(models.ActionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tindak lanjut tidak ditemukan")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "status" and value is not None:
            value = models.ActionStatusEnum(value)
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


# ============================================================
#  BUKTI / DOKUMENTASI (foto)
# ============================================================
@app.post("/api/meetings/{meeting_id}/bukti", response_model=List[schemas.DocumentationOut])
def upload_bukti(meeting_id: int, files: List[UploadFile] = File(...),
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")

    hasil = []
    for f in files:
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Berkas {f.filename} bukan gambar")
        saved_path = _save_upload(f, settings.BUKTI_DIR, settings.MAX_IMAGE_MB)
        doc = models.Documentation(meeting_id=meeting_id, file_path=saved_path.name, keterangan="")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        hasil.append(schemas.DocumentationOut(
            id=doc.id, file_path=doc.file_path, keterangan=doc.keterangan,
            url=f"/media/bukti/{doc.file_path}",
        ))
    return hasil


@app.delete("/api/bukti/{doc_id}")
def delete_bukti(doc_id: int, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    doc = db.query(models.Documentation).filter(models.Documentation.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumentasi tidak ditemukan")
    (settings.BUKTI_DIR / doc.file_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@app.delete("/api/materi/{materi_id}")
def delete_materi(materi_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    m = db.query(models.MeetingMaterial).filter(models.MeetingMaterial.id == materi_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
    (settings.MATERI_DIR / m.file_path).unlink(missing_ok=True)
    db.delete(m)
    db.commit()
    return {"ok": True}


# ============================================================
#  EXPORT - Word & PDF
# ============================================================
def _build_export_docx(db: Session, meeting_id: int) -> tuple:
    """Menyusun dokumen Word untuk sebuah rapat. Dipakai oleh export Word & PDF."""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    summary = db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).first()
    if not summary:
        raise HTTPException(status_code=400, detail="Rapat belum diproses AI, tidak ada yang bisa diekspor")

    transcript = db.query(models.Transcript).filter(models.Transcript.meeting_id == meeting_id).first()
    actions = db.query(models.ActionItem).filter(models.ActionItem.meeting_id == meeting_id).all()
    docs = db.query(models.Documentation).filter(models.Documentation.meeting_id == meeting_id).all()
    pimpinan = db.query(models.Pegawai).filter(models.Pegawai.id == meeting.pimpinan_id).first()
    notulis = db.query(models.Pegawai).filter(models.Pegawai.id == meeting.notulis_id).first()
    peserta = db.query(models.Pegawai).filter(
        models.Pegawai.id.in_(json.loads(meeting.peserta_ids or "[]"))
    ).all()
    kepala = _get_kepala_bps(db)

    output_path = settings.EXPORT_DIR / f"notulensi_{meeting_id}_{uuid.uuid4().hex[:8]}.docx"
    try:
        build_notulensi_docx(
            meeting=meeting,
            transcript_text=transcript.teks_transkripsi if transcript else "",
            ringkasan=json.loads(summary.ringkasan),
            keputusan=json.loads(summary.keputusan),
            tindak_lanjut=[{
                "deskripsi": a.deskripsi, "penanggung_jawab": a.penanggung_jawab,
                "deadline": a.deadline, "status": a.status.value,
            } for a in actions],
            peserta_list=peserta,
            pimpinan=pimpinan, notulis=notulis, kepala=kepala,
            dokumentasi_files=[{"path": settings.BUKTI_DIR / d.file_path, "keterangan": d.keterangan} for d in docs],
            output_path=output_path,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyusun dokumen Word: {e}")

    db.add(models.Archive(meeting_id=meeting_id, file_docx=output_path.name))
    db.commit()
    return meeting, output_path


@app.get("/api/meetings/{meeting_id}/export/docx")
def export_docx(meeting_id: int, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    meeting, output_path = _build_export_docx(db, meeting_id)
    return FileResponse(
        path=output_path,
        filename=f"Notula - {meeting.judul_rapat}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/meetings/{meeting_id}/export/pdf")
def export_pdf(meeting_id: int, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    meeting, docx_path = _build_export_docx(db, meeting_id)
    try:
        pdf_path = convert_docx_to_pdf(docx_path, settings.EXPORT_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    db.add(models.Archive(meeting_id=meeting_id, file_docx=pdf_path.name))
    db.commit()
    return FileResponse(
        path=pdf_path,
        filename=f"Notula - {meeting.judul_rapat}.pdf",
        media_type="application/pdf",
    )


# ============================================================
#  DASHBOARD
# ============================================================
@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    total_rapat = db.query(models.Meeting).count()
    total_arsip = db.query(models.Archive).count()

    today = date.today()
    bulan_ini_prefix = today.strftime("%Y-%m")
    notulensi_bulan_ini = db.query(models.Meeting).filter(
        models.Meeting.tanggal.like(f"{bulan_ini_prefix}%"),
        models.Meeting.status == models.StatusEnum.selesai,
    ).count()

    rows = db.query(models.Meeting.tanggal).all()
    counts = {}
    for (tgl,) in rows:
        key = tgl[:7] if tgl else "unknown"
        counts[key] = counts.get(key, 0) + 1

    return schemas.DashboardStats(
        total_rapat=total_rapat, notulensi_bulan_ini=notulensi_bulan_ini,
        total_arsip=total_arsip,
        grafik_per_bulan=dict(sorted(counts.items())),
    )


# ============================================================
#  BERKAS STATIS
# ============================================================
app.mount("/media/bukti", StaticFiles(directory=str(settings.BUKTI_DIR)), name="bukti")
app.mount("/media/materi", StaticFiles(directory=str(settings.MATERI_DIR)), name="materi")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
