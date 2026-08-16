"""Alur rapat baru (lihat RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md).

Seluruh endpoint di sini hidup berdampingan dengan /api/meetings lama
(lihat main.py) - keduanya beroperasi pada tabel `meetings` yang sama
tapi memakai kolom & tabel anak yang berbeda (lihat models.py). Endpoint
lama tidak diubah oleh modul ini.

Aturan penting: jangan pernah menulis `meeting.lifecycle_status = ...`
langsung di sini - selalu lewat `rapat_lifecycle.transisi()`.
"""
import json
import threading
import uuid
from types import SimpleNamespace
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_roles, assert_can_write_meeting
from ..config import settings
from ..database import get_db, SessionLocal
from ..rapat_lifecycle import transisi, pastikan_status, tolak_jika_diarsipkan
from ..services.docx_export import build_notulensi_docx, build_pendahuluan_text
from ..services.pdf_export import convert_docx_to_pdf
from ..services.summarizer import summarize_transcript
from ..services.transcription import transcribe_audio
from ..utils.storage import _save_upload
from ..utils.tz import now_wib

router = APIRouter(prefix="/api/rapat", tags=["rapat"])

S = models.MeetingLifecycleStatus


# ============================================================
#  HELPER
# ============================================================
def _get_rapat_or_404(db: Session, rapat_id: int) -> models.Meeting:
    meeting = db.query(models.Meeting).filter(models.Meeting.id == rapat_id).first()
    if not meeting or meeting.lifecycle_status is None:
        raise HTTPException(status_code=404, detail="Rapat tidak ditemukan")
    return meeting


def _peserta_nama_gabungan(db: Session, meeting_id: int) -> str:
    rows = db.query(models.MeetingPeserta).filter(models.MeetingPeserta.meeting_id == meeting_id).all()
    names = []
    for p in rows:
        if p.user_id:
            u = db.query(models.User).filter(models.User.id == p.user_id).first()
            if u:
                names.append(u.nama)
        elif p.nama_manual:
            names.append(p.nama_manual)
    return ", ".join(names)


def _to_rapat_out(db: Session, meeting: models.Meeting) -> schemas.RapatOut:
    pimpinan = db.query(models.User).filter(models.User.id == meeting.pimpinan_id).first() if meeting.pimpinan_id else None
    notulis = db.query(models.User).filter(models.User.id == meeting.notulis_id).first() if meeting.notulis_id else None

    jumlah_peserta = db.query(models.MeetingPeserta).filter(models.MeetingPeserta.meeting_id == meeting.id).count()
    jumlah_hadir = (
        db.query(models.MeetingKehadiran)
        .join(models.MeetingPeserta, models.MeetingKehadiran.peserta_id == models.MeetingPeserta.id)
        .filter(
            models.MeetingPeserta.meeting_id == meeting.id,
            models.MeetingKehadiran.status_kehadiran == models.StatusKehadiranEnum.hadir,
        )
        .count()
    )
    jumlah_dokumen = db.query(models.MeetingDokumen).filter(
        models.MeetingDokumen.meeting_id == meeting.id,
        models.MeetingDokumen.status == models.StatusDokumenEnum.aktif,
    ).count()
    jumlah_rekaman = db.query(models.MeetingRekaman).filter(models.MeetingRekaman.meeting_id == meeting.id).count()
    transkrip = (
        db.query(models.MeetingTranskrip)
        .filter(models.MeetingTranskrip.meeting_id == meeting.id)
        .order_by(models.MeetingTranskrip.id.desc())
        .first()
    )
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == meeting.id).first()

    return schemas.RapatOut(
        id=meeting.id, judul_rapat=meeting.judul_rapat, tanggal=meeting.tanggal,
        unit_kerja=meeting.unit_kerja, waktu_mulai=meeting.waktu_mulai, waktu_selesai=meeting.waktu_selesai,
        lokasi=meeting.lokasi, jenis_media=meeting.jenis_media.value if meeting.jenis_media else None,
        agenda=meeting.agenda, catatan_notulis=meeting.catatan_notulis,
        pimpinan=schemas.PegawaiOut.model_validate(pimpinan) if pimpinan else None,
        notulis=schemas.PegawaiOut.model_validate(notulis) if notulis else None,
        lifecycle_status=meeting.lifecycle_status.value,
        waktu_mulai_aktual=meeting.waktu_mulai_aktual, waktu_selesai_aktual=meeting.waktu_selesai_aktual,
        alasan_pembatalan=meeting.alasan_pembatalan, dibuat_pada=meeting.created_at,
        ringkasan=schemas.RapatRingkasan(
            jumlah_peserta=jumlah_peserta, jumlah_hadir=jumlah_hadir,
            jumlah_dokumen=jumlah_dokumen, jumlah_rekaman=jumlah_rekaman,
            status_transkrip=transkrip.status.value if transkrip else None,
            status_notula=notula.status.value if notula else None,
        ),
    )


def _to_peserta_out(p: models.MeetingPeserta) -> schemas.PesertaOut:
    return schemas.PesertaOut(
        id=p.id,
        pegawai=schemas.PegawaiOut.model_validate(p.user) if p.user else None,
        nama_manual=p.nama_manual, jabatan_manual=p.jabatan_manual, instansi_manual=p.instansi_manual,
        peran=p.peran.value, sumber=p.sumber.value, ditambahkan_pada=p.ditambahkan_pada,
        kehadiran=schemas.KehadiranOut.model_validate(p.kehadiran) if p.kehadiran else None,
    )


def _to_notula_out(db: Session, notula: models.MeetingNotula) -> schemas.NotulaOut:
    difinal_nama = None
    if notula.difinalisasi_oleh:
        u = db.query(models.User).filter(models.User.id == notula.difinalisasi_oleh).first()
        difinal_nama = u.nama if u else None
    return schemas.NotulaOut(
        id=notula.id, status=notula.status.value,
        pendahuluan=notula.pendahuluan,
        ringkasan=json.loads(notula.ringkasan or "[]"),
        pertanyaan_jawaban=json.loads(notula.pertanyaan_jawaban or "[]"),
        keputusan=json.loads(notula.keputusan or "[]"),
        catatan_tambahan=notula.catatan_tambahan, sumber=notula.sumber.value if notula.sumber else None,
        versi=notula.versi, difinalisasi_oleh=difinal_nama, difinalisasi_pada=notula.difinalisasi_pada,
        tindak_lanjut=[schemas.TindakLanjutOut.model_validate(t) for t in notula.tindak_lanjut],
    )


def _get_kepala_bps(db: Session):
    return db.query(models.User).filter(models.User.jabatan.ilike("%Kepala BPS%")).first()


def _snapshot_notula(notula: models.MeetingNotula) -> str:
    return json.dumps({
        "pendahuluan": notula.pendahuluan,
        "ringkasan": json.loads(notula.ringkasan or "[]"),
        "pertanyaan_jawaban": json.loads(notula.pertanyaan_jawaban or "[]"),
        "keputusan": json.loads(notula.keputusan or "[]"),
        "catatan_tambahan": notula.catatan_tambahan,
        "tindak_lanjut": [
            {"deskripsi": t.deskripsi, "penanggung_jawab": t.penanggung_jawab,
             "deadline": t.deadline, "status": t.status.value}
            for t in notula.tindak_lanjut
        ],
    }, ensure_ascii=False)


# ============================================================
#  RAPAT INTI
# ============================================================
@router.post("", response_model=schemas.RapatOut)
def create_rapat(payload: schemas.RapatCreate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    """Pembuatan rapat minimum - hanya judul_rapat & tanggal wajib, semua
    field lain (termasuk peserta/dokumen/rekaman) dilengkapi kapan saja
    lewat endpoint masing-masing, sebelum/selama/setelah rapat.

    Siapapun yang login boleh membuat rapat (admin atau pegawai) - pembuat
    otomatis tercatat sebagai notulis_id rapat ini (lihat auth.can_write_meeting),
    admin dapat menugaskan ulang notulis kapan saja lewat PATCH /{rapat_id}."""
    jenis_media = None
    if payload.jenis_media:
        try:
            jenis_media = models.JenisMediaEnum(payload.jenis_media)
        except ValueError:
            raise HTTPException(status_code=400, detail="jenis_media tidak valid")

    meeting = models.Meeting(
        unit_kerja=payload.unit_kerja or settings.UNIT_KERJA_DEFAULT,
        judul_rapat=payload.judul_rapat, tanggal=payload.tanggal,
        waktu_mulai=payload.waktu_mulai, waktu_selesai=payload.waktu_selesai,
        lokasi=payload.lokasi, agenda=payload.agenda, catatan_notulis=payload.catatan_notulis,
        pimpinan_id=payload.pimpinan_id,
        notulis_id=current_user.id,
        jenis_media=jenis_media,
        lifecycle_status=S.draft,
        user_id=current_user.id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    # Satu-satunya tempat yang menulis status di luar rapat_lifecycle.transisi():
    # ini "kelahiran" rapat, tidak ada status asal untuk divalidasi transisi().
    db.add(models.MeetingStatusLog(
        meeting_id=meeting.id, status_dari=None, status_ke=S.draft.value,
        diubah_oleh=current_user.id, catatan="Rapat dibuat",
    ))
    db.commit()
    return _to_rapat_out(db, meeting)


@router.get("", response_model=List[schemas.RapatOut])
def list_rapat(q: str = "", status: str = "", hanya_peserta_saya: bool = False, peran: str = "",
                db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Meeting).filter(models.Meeting.lifecycle_status.is_not(None))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(models.Meeting.judul_rapat.ilike(like))
    if status.strip():
        try:
            query = query.filter(models.Meeting.lifecycle_status == S(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Status tidak valid")
    if hanya_peserta_saya:
        # Dipakai Dashboard & Arsip Notula supaya role pegawai hanya melihat
        # rapat yang benar-benar mengundang/melibatkan dirinya sebagai peserta.
        peserta_query = db.query(models.MeetingPeserta.meeting_id).filter(
            models.MeetingPeserta.user_id == current_user.id)
        if peran.strip():
            # Dipakai widget "Undangan Rapat" di Dashboard supaya hanya rapat
            # yang mengundang pegawai ini secara eksplisit (peran=undangan)
            # yang muncul, terpisah dari daftar "Rapat Saya" yang lebih umum.
            try:
                peserta_query = peserta_query.filter(
                    models.MeetingPeserta.peran == models.PeranPesertaEnum(peran))
            except ValueError:
                raise HTTPException(status_code=400, detail="Peran tidak valid")
        peserta_meeting_ids = peserta_query.subquery()
        query = query.filter(models.Meeting.id.in_(peserta_meeting_ids))
    elif current_user.role != models.RoleEnum.admin:
        # Halaman "Rapat" (kelola aktif) - pegawai tidak punya fitur Rapat
        # penuh (lihat item 37), kecuali untuk rapat yang dia sendiri ditunjuk
        # sebagai notulis (lihat auth.can_write_meeting). Arsip notula tetap
        # dijangkau lewat hanya_peserta_saya di atas, terlepas dari ini.
        query = query.filter(models.Meeting.notulis_id == current_user.id)
    meetings = query.order_by(models.Meeting.tanggal.desc()).all()
    return [_to_rapat_out(db, m) for m in meetings]


@router.get("/{rapat_id}", response_model=schemas.RapatOut)
def get_rapat(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _to_rapat_out(db, _get_rapat_or_404(db, rapat_id))


@router.patch("/{rapat_id}", response_model=schemas.RapatOut)
def update_rapat(rapat_id: int, payload: schemas.RapatUpdate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    data = payload.model_dump(exclude_unset=True)
    if "jenis_media" in data and data["jenis_media"] is not None:
        try:
            data["jenis_media"] = models.JenisMediaEnum(data["jenis_media"])
        except ValueError:
            raise HTTPException(status_code=400, detail="jenis_media tidak valid")
    for field, value in data.items():
        setattr(meeting, field, value)
    db.commit()
    return _to_rapat_out(db, meeting)


@router.delete("/{rapat_id}")
def delete_rapat(rapat_id: int, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    # Tidak ada cascade ORM di sisi Meeting untuk tabel-tabel baru (lihat models.py),
    # jadi anak dihapus manual dulu sebelum induknya.
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if notula:
        db.query(models.MeetingTindakLanjut).filter(models.MeetingTindakLanjut.notula_id == notula.id).delete()
        db.query(models.MeetingNotulaRiwayat).filter(models.MeetingNotulaRiwayat.notula_id == notula.id).delete()
        db.delete(notula)
    for peserta in db.query(models.MeetingPeserta).filter(models.MeetingPeserta.meeting_id == rapat_id).all():
        db.query(models.MeetingKehadiran).filter(models.MeetingKehadiran.peserta_id == peserta.id).delete()
        db.delete(peserta)
    for dok in db.query(models.MeetingDokumen).filter(models.MeetingDokumen.meeting_id == rapat_id).all():
        (settings.DOKUMEN_DIR / dok.file_path).unlink(missing_ok=True)
    for rek in db.query(models.MeetingRekaman).filter(models.MeetingRekaman.meeting_id == rapat_id).all():
        if rek.file_path:
            (settings.REKAMAN_DIR / rek.file_path).unlink(missing_ok=True)
    for tbl in (models.MeetingDokumen, models.MeetingRekaman, models.MeetingTranskrip, models.MeetingStatusLog):
        db.query(tbl).filter(tbl.meeting_id == rapat_id).delete()
    db.commit()
    db.delete(meeting)
    db.commit()
    return {"ok": True}


# ============================================================
#  TRANSISI STATUS
# ============================================================
@router.post("/{rapat_id}/jadwalkan", response_model=schemas.RapatOut)
def jadwalkan_rapat(rapat_id: int, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    transisi(db, meeting, "jadwalkan", actor=current_user)
    return _to_rapat_out(db, meeting)


@router.post("/{rapat_id}/mulai", response_model=schemas.RapatOut)
def mulai_rapat(rapat_id: int, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    meeting.waktu_mulai_aktual = now_wib()
    transisi(db, meeting, "mulai", actor=current_user)
    return _to_rapat_out(db, meeting)


@router.post("/{rapat_id}/batalkan", response_model=schemas.RapatOut)
def batalkan_rapat(rapat_id: int, payload: schemas.AlasanRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    meeting.alasan_pembatalan = payload.alasan
    # rekaman aktif ikut dihentikan (dicatat sebagai draft, tidak dihapus)
    for seg in db.query(models.MeetingRekaman).filter(
        models.MeetingRekaman.meeting_id == rapat_id,
        models.MeetingRekaman.status.in_([models.StatusRekamanEnum.merekam, models.StatusRekamanEnum.dijeda]),
    ).all():
        seg.status = models.StatusRekamanEnum.berhenti
        seg.selesai_pada = now_wib()
    transisi(db, meeting, "batalkan", actor=current_user, catatan=payload.alasan)
    return _to_rapat_out(db, meeting)


@router.post("/{rapat_id}/akhiri", response_model=schemas.RapatOut)
def akhiri_rapat(rapat_id: int, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    meeting.waktu_selesai_aktual = now_wib()
    for seg in db.query(models.MeetingRekaman).filter(
        models.MeetingRekaman.meeting_id == rapat_id,
        models.MeetingRekaman.status.in_([models.StatusRekamanEnum.merekam, models.StatusRekamanEnum.dijeda]),
    ).all():
        seg.status = models.StatusRekamanEnum.berhenti
        seg.selesai_pada = now_wib()
    transisi(db, meeting, "akhiri", actor=current_user)
    return _to_rapat_out(db, meeting)


# ============================================================
#  PESERTA & KEHADIRAN
# ============================================================
@router.post("/{rapat_id}/peserta", response_model=schemas.PesertaOut)
def tambah_peserta(rapat_id: int, payload: schemas.PesertaCreate, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    if not payload.user_id and not payload.nama_manual:
        raise HTTPException(status_code=400, detail="Isi user_id atau nama_manual")
    try:
        peran = models.PeranPesertaEnum(payload.peran)
    except ValueError:
        raise HTTPException(status_code=400, detail="peran tidak valid")
    sumber = models.SumberPesertaEnum.diundang if meeting.lifecycle_status in (S.draft, S.dijadwalkan) \
        else models.SumberPesertaEnum.tambahan
    p = models.MeetingPeserta(
        meeting_id=rapat_id, user_id=payload.user_id,
        nama_manual=payload.nama_manual, jabatan_manual=payload.jabatan_manual,
        instansi_manual=payload.instansi_manual, peran=peran, sumber=sumber,
        ditambahkan_oleh=current_user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_peserta_out(p)


@router.get("/{rapat_id}/peserta", response_model=List[schemas.PesertaOut])
def list_peserta(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _get_rapat_or_404(db, rapat_id)
    rows = db.query(models.MeetingPeserta).filter(models.MeetingPeserta.meeting_id == rapat_id).all()
    return [_to_peserta_out(p) for p in rows]


@router.patch("/{rapat_id}/peserta/{peserta_id}", response_model=schemas.PesertaOut)
def edit_peserta(rapat_id: int, peserta_id: int, payload: schemas.PesertaUpdate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    p = db.query(models.MeetingPeserta).filter(
        models.MeetingPeserta.id == peserta_id, models.MeetingPeserta.meeting_id == rapat_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Peserta tidak ditemukan")
    data = payload.model_dump(exclude_unset=True)
    if "peran" in data and data["peran"] is not None:
        try:
            data["peran"] = models.PeranPesertaEnum(data["peran"])
        except ValueError:
            raise HTTPException(status_code=400, detail="peran tidak valid")
    for field, value in data.items():
        setattr(p, field, value)
    db.commit()
    return _to_peserta_out(p)


@router.delete("/{rapat_id}/peserta/{peserta_id}")
def hapus_peserta(rapat_id: int, peserta_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    p = db.query(models.MeetingPeserta).filter(
        models.MeetingPeserta.id == peserta_id, models.MeetingPeserta.meeting_id == rapat_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Peserta tidak ditemukan")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.patch("/{rapat_id}/peserta/{peserta_id}/kehadiran", response_model=schemas.PesertaOut)
def catat_kehadiran(rapat_id: int, peserta_id: int, payload: schemas.KehadiranUpdate, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    p = db.query(models.MeetingPeserta).filter(
        models.MeetingPeserta.id == peserta_id, models.MeetingPeserta.meeting_id == rapat_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Peserta tidak ditemukan")
    try:
        status_kehadiran = models.StatusKehadiranEnum(payload.status_kehadiran)
    except ValueError:
        raise HTTPException(status_code=400, detail="status_kehadiran tidak valid")

    # Koreksi dianggap "pasca-rapat" begitu rapat sudah lewat BERLANGSUNG -
    # ditandai untuk audit (badge "Dikoreksi"), bukan diblokir.
    pasca_rapat = meeting.lifecycle_status not in (S.draft, S.dijadwalkan, S.berlangsung)

    kehadiran = p.kehadiran
    if not kehadiran:
        kehadiran = models.MeetingKehadiran(peserta_id=p.id)
        db.add(kehadiran)
    kehadiran.status_kehadiran = status_kehadiran
    kehadiran.waktu_hadir = payload.waktu_hadir or (now_wib() if status_kehadiran == models.StatusKehadiranEnum.hadir
                                                     else kehadiran.waktu_hadir)
    kehadiran.waktu_keluar = payload.waktu_keluar
    kehadiran.keterangan = payload.keterangan
    kehadiran.dicatat_oleh = current_user.id
    kehadiran.dicatat_pada = now_wib()
    if pasca_rapat:
        kehadiran.diedit_pasca_rapat = True
    db.commit()
    db.refresh(p)
    return _to_peserta_out(p)


@router.post("/{rapat_id}/peserta/walkin", response_model=schemas.PesertaOut)
def tambah_walkin(rapat_id: int, payload: schemas.WalkinCreate, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    """Peserta yang datang langsung tanpa terdaftar - satu aksi, langsung
    tercatat sebagai peserta (sumber=walk_in) dan hadir."""
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    p = models.MeetingPeserta(
        meeting_id=rapat_id, nama_manual=payload.nama_manual,
        jabatan_manual=payload.jabatan_manual, instansi_manual=payload.instansi_manual,
        peran=models.PeranPesertaEnum.peserta, sumber=models.SumberPesertaEnum.walk_in,
        ditambahkan_oleh=current_user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    kehadiran = models.MeetingKehadiran(
        peserta_id=p.id, status_kehadiran=models.StatusKehadiranEnum.hadir,
        waktu_hadir=payload.waktu_hadir or now_wib(), keterangan=payload.keterangan,
        dicatat_oleh=current_user.id,
    )
    db.add(kehadiran)
    db.commit()
    db.refresh(p)
    return _to_peserta_out(p)


# ============================================================
#  DOKUMEN
# ============================================================
@router.post("/{rapat_id}/dokumen", response_model=List[schemas.DokumenOut])
def upload_dokumen(rapat_id: int, jenis: str = Form("lainnya"), files: List[UploadFile] = File(...),
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    try:
        jenis_enum = models.JenisDokumenEnum(jenis)
    except ValueError:
        raise HTTPException(status_code=400, detail="jenis dokumen tidak valid")

    pasca_rapat = meeting.lifecycle_status not in (S.draft, S.dijadwalkan, S.berlangsung)
    hasil = []
    for f in files:
        if not f.filename:
            continue
        # Reupload nama file yang sama -> versi naik, versi lama ditandai diganti (bukan dihapus).
        lama = db.query(models.MeetingDokumen).filter(
            models.MeetingDokumen.meeting_id == rapat_id,
            models.MeetingDokumen.nama_file == f.filename,
            models.MeetingDokumen.status == models.StatusDokumenEnum.aktif,
        ).first()
        versi_baru = 1
        if lama:
            lama.status = models.StatusDokumenEnum.diganti
            versi_baru = lama.versi + 1

        saved_path = _save_upload(f, settings.DOKUMEN_DIR, settings.MAX_MATERI_MB)
        dok = models.MeetingDokumen(
            meeting_id=rapat_id, nama_file=f.filename, jenis=jenis_enum,
            file_path=saved_path.name, mime_type=f.content_type,
            ukuran_bytes=saved_path.stat().st_size, versi=versi_baru,
            diunggah_pasca_rapat=pasca_rapat, diunggah_oleh=current_user.id,
        )
        db.add(dok)
        db.commit()
        db.refresh(dok)
        hasil.append(schemas.DokumenOut(
            id=dok.id, nama_file=dok.nama_file, jenis=dok.jenis.value, url=f"/media/dokumen/{dok.file_path}",
            mime_type=dok.mime_type, ukuran_bytes=dok.ukuran_bytes, versi=dok.versi,
            status=dok.status.value, diunggah_pasca_rapat=dok.diunggah_pasca_rapat, diunggah_pada=dok.diunggah_pada,
        ))
    return hasil


@router.get("/{rapat_id}/dokumen", response_model=List[schemas.DokumenOut])
def list_dokumen(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _get_rapat_or_404(db, rapat_id)
    rows = db.query(models.MeetingDokumen).filter(
        models.MeetingDokumen.meeting_id == rapat_id,
        models.MeetingDokumen.status != models.StatusDokumenEnum.dihapus,
    ).order_by(models.MeetingDokumen.diunggah_pada.desc()).all()
    return [
        schemas.DokumenOut(
            id=d.id, nama_file=d.nama_file, jenis=d.jenis.value, url=f"/media/dokumen/{d.file_path}",
            mime_type=d.mime_type, ukuran_bytes=d.ukuran_bytes, versi=d.versi,
            status=d.status.value, diunggah_pasca_rapat=d.diunggah_pasca_rapat, diunggah_pada=d.diunggah_pada,
        ) for d in rows
    ]


@router.delete("/{rapat_id}/dokumen/{dokumen_id}")
def hapus_dokumen(rapat_id: int, dokumen_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    d = db.query(models.MeetingDokumen).filter(
        models.MeetingDokumen.id == dokumen_id, models.MeetingDokumen.meeting_id == rapat_id
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    d.status = models.StatusDokumenEnum.dihapus   # soft delete - berkas fisik tetap ada untuk audit
    db.commit()
    return {"ok": True}


# ============================================================
#  REKAMAN
# ============================================================
@router.post("/{rapat_id}/rekaman/mulai", response_model=schemas.RekamanOut)
def mulai_rekaman(rapat_id: int, file: Optional[UploadFile] = File(None), db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    """Mulai segmen rekaman baru. Bila `file` disertakan (upload berkas audio
    yang sudah ada, mis. hasil rekaman HP), segmen langsung berstatus siap -
    dipakai untuk alur "Upload Berkas Audio" sebagai alternatif rekam langsung.
    Rekam LANGSUNG (tanpa file) hanya masuk akal saat rapat BERLANGSUNG, tapi
    upload berkas yang sudah ada boleh kapan saja (kecuali sudah diarsipkan) -
    lihat §7/§9 rancangan (edge case #7: dokumen/rekaman pasca-rapat)."""
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    if file is not None and file.filename:
        tolak_jika_diarsipkan(meeting)
    else:
        pastikan_status(meeting, S.berlangsung)
    segmen_ke = (db.query(models.MeetingRekaman)
                 .filter(models.MeetingRekaman.meeting_id == rapat_id).count()) + 1

    if file is not None and file.filename:
        saved_path = _save_upload(file, settings.REKAMAN_DIR, settings.MAX_UPLOAD_MB)
        seg = models.MeetingRekaman(
            meeting_id=rapat_id, segmen_ke=segmen_ke, file_path=saved_path.name,
            format=saved_path.suffix.lstrip("."), ukuran_bytes=saved_path.stat().st_size,
            status=models.StatusRekamanEnum.siap, direkam_oleh=current_user.id,
            selesai_pada=now_wib(),
        )
    else:
        seg = models.MeetingRekaman(
            meeting_id=rapat_id, segmen_ke=segmen_ke,
            status=models.StatusRekamanEnum.merekam, direkam_oleh=current_user.id,
        )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return schemas.RekamanOut(
        id=seg.id, segmen_ke=seg.segmen_ke, status=seg.status.value, durasi_detik=seg.durasi_detik,
        ukuran_bytes=seg.ukuran_bytes, url=f"/media/rekaman/{seg.file_path}" if seg.file_path else "",
        pesan_error=seg.pesan_error, mulai_pada=seg.mulai_pada, selesai_pada=seg.selesai_pada,
    )


def _get_rekaman_or_404(db: Session, rapat_id: int, rekaman_id: int) -> models.MeetingRekaman:
    seg = db.query(models.MeetingRekaman).filter(
        models.MeetingRekaman.id == rekaman_id, models.MeetingRekaman.meeting_id == rapat_id
    ).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segmen rekaman tidak ditemukan")
    return seg


@router.post("/{rapat_id}/rekaman/{rekaman_id}/pause")
def pause_rekaman(rapat_id: int, rekaman_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    seg = _get_rekaman_or_404(db, rapat_id, rekaman_id)
    if seg.status != models.StatusRekamanEnum.merekam:
        raise HTTPException(status_code=400, detail="Segmen ini tidak sedang merekam")
    seg.status = models.StatusRekamanEnum.dijeda
    db.commit()
    return {"ok": True}


@router.post("/{rapat_id}/rekaman/{rekaman_id}/resume")
def resume_rekaman(rapat_id: int, rekaman_id: int, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    seg = _get_rekaman_or_404(db, rapat_id, rekaman_id)
    if seg.status != models.StatusRekamanEnum.dijeda:
        raise HTTPException(status_code=400, detail="Segmen ini tidak sedang dijeda")
    seg.status = models.StatusRekamanEnum.merekam
    db.commit()
    return {"ok": True}


@router.post("/{rapat_id}/rekaman/{rekaman_id}/selesai", response_model=schemas.RekamanOut)
def selesaikan_rekaman(rapat_id: int, rekaman_id: int, file: UploadFile = File(...),
                        durasi_detik: float = Form(0), db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    seg = _get_rekaman_or_404(db, rapat_id, rekaman_id)
    if seg.status not in (models.StatusRekamanEnum.merekam, models.StatusRekamanEnum.dijeda):
        raise HTTPException(status_code=400, detail="Segmen ini sudah diselesaikan")
    try:
        saved_path = _save_upload(file, settings.REKAMAN_DIR, settings.MAX_UPLOAD_MB)
        seg.file_path = saved_path.name
        seg.format = saved_path.suffix.lstrip(".")
        seg.ukuran_bytes = saved_path.stat().st_size
        seg.durasi_detik = durasi_detik
        seg.status = models.StatusRekamanEnum.siap
    except Exception as e:
        seg.status = models.StatusRekamanEnum.gagal
        seg.pesan_error = str(e)
    seg.selesai_pada = now_wib()
    db.commit()
    db.refresh(seg)
    return schemas.RekamanOut(
        id=seg.id, segmen_ke=seg.segmen_ke, status=seg.status.value, durasi_detik=seg.durasi_detik,
        ukuran_bytes=seg.ukuran_bytes, url=f"/media/rekaman/{seg.file_path}" if seg.file_path else "",
        pesan_error=seg.pesan_error, mulai_pada=seg.mulai_pada, selesai_pada=seg.selesai_pada,
    )


@router.get("/{rapat_id}/rekaman", response_model=List[schemas.RekamanOut])
def list_rekaman(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _get_rapat_or_404(db, rapat_id)
    rows = db.query(models.MeetingRekaman).filter(
        models.MeetingRekaman.meeting_id == rapat_id
    ).order_by(models.MeetingRekaman.segmen_ke).all()
    return [
        schemas.RekamanOut(
            id=s.id, segmen_ke=s.segmen_ke, status=s.status.value, durasi_detik=s.durasi_detik,
            ukuran_bytes=s.ukuran_bytes, url=f"/media/rekaman/{s.file_path}" if s.file_path else "",
            pesan_error=s.pesan_error, mulai_pada=s.mulai_pada, selesai_pada=s.selesai_pada,
        ) for s in rows
    ]


# ============================================================
#  TRANSKRIPSI - proses STT berjalan di background thread, pola sama
#  seperti _run_ai_pipeline di main.py (lama).
# ============================================================
def _run_transkripsi(meeting_id: int, transkrip_id: int):
    db = SessionLocal()
    try:
        meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
        transkrip = db.query(models.MeetingTranskrip).filter(models.MeetingTranskrip.id == transkrip_id).first()
        if not meeting or not transkrip:
            return
        segmen = db.query(models.MeetingRekaman).filter(
            models.MeetingRekaman.meeting_id == meeting_id,
            models.MeetingRekaman.status == models.StatusRekamanEnum.siap,
        ).order_by(models.MeetingRekaman.segmen_ke).all()
        try:
            if not segmen:
                raise RuntimeError("Tidak ada rekaman siap untuk ditranskripsi")
            bagian = []
            for seg in segmen:
                path = settings.REKAMAN_DIR / seg.file_path
                teks = transcribe_audio(path)
                label = f"--- Segmen {seg.segmen_ke} ---\n" if len(segmen) > 1 else ""
                bagian.append(label + teks)
            transkrip.teks = "\n\n".join(bagian)
            transkrip.status = models.StatusTranskripEnum.siap
            transkrip.selesai_pada = now_wib()
            db.commit()
            # Rapat yang masih BERLANGSUNG saat transkripsi dimulai (item 38)
            # tidak pernah dipindah ke DIPROSES - lihat proses_transkripsi() -
            # jadi tidak ada transisi lifecycle untuk dibalikkan di sini.
            if meeting.lifecycle_status == S.diproses:
                transisi(db, meeting, "transkripsi_selesai", actor=None, catatan="Transkripsi otomatis berhasil")
        except Exception as e:
            transkrip.status = models.StatusTranskripEnum.gagal
            transkrip.pesan_error = str(e)
            transkrip.selesai_pada = now_wib()
            db.commit()
            if meeting.lifecycle_status == S.diproses:
                transisi(db, meeting, "transkripsi_selesai", actor=None, catatan=f"Transkripsi gagal: {e}")
    finally:
        db.close()


@router.post("/{rapat_id}/transkripsi/proses", response_model=schemas.TranskripOut)
def proses_transkripsi(rapat_id: int, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    if meeting.lifecycle_status not in (S.berlangsung, S.selesai):
        raise HTTPException(status_code=400, detail="Transkripsi hanya bisa dimulai saat rapat berlangsung atau sudah selesai")
    ada_siap = db.query(models.MeetingRekaman).filter(
        models.MeetingRekaman.meeting_id == rapat_id,
        models.MeetingRekaman.status == models.StatusRekamanEnum.siap,
    ).count() > 0
    if not ada_siap:
        raise HTTPException(status_code=400, detail="Belum ada rekaman siap untuk diproses")

    transkrip = models.MeetingTranskrip(
        meeting_id=rapat_id, sumber=models.SumberTranskripEnum.stt,
        status=models.StatusTranskripEnum.berjalan, mulai_pada=now_wib(),
    )
    db.add(transkrip)
    # Rapat yang masih BERLANGSUNG tetap BERLANGSUNG (lihat catatan di
    # _TRANSITIONS["mulai_transkripsi"], rapat_lifecycle.py) - hanya rapat
    # yang sudah SELESAI yang benar-benar pindah ke DIPROSES.
    if meeting.lifecycle_status == S.selesai:
        transisi(db, meeting, "mulai_transkripsi", actor=current_user)
    db.commit()
    db.refresh(transkrip)

    threading.Thread(target=_run_transkripsi, args=(rapat_id, transkrip.id), daemon=True).start()
    return schemas.TranskripOut.model_validate(transkrip)


@router.post("/{rapat_id}/transkripsi/manual", response_model=schemas.RapatOut)
def transkripsi_manual(rapat_id: int, payload: schemas.TranskripManualIn, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    pastikan_status(meeting, S.selesai)
    transkrip = models.MeetingTranskrip(
        meeting_id=rapat_id, sumber=models.SumberTranskripEnum.manual,
        status=models.StatusTranskripEnum.siap, teks=payload.teks,
        mulai_pada=now_wib(), selesai_pada=now_wib(),
    )
    db.add(transkrip)
    db.commit()
    return _to_rapat_out(db, meeting)


@router.patch("/{rapat_id}/transkripsi", response_model=schemas.TranskripOut)
def edit_transkripsi(rapat_id: int, payload: schemas.TranskripUpdate, db: Session = Depends(get_db),
                      current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    transkrip = (db.query(models.MeetingTranskrip)
                 .filter(models.MeetingTranskrip.meeting_id == rapat_id)
                 .order_by(models.MeetingTranskrip.id.desc()).first())
    if not transkrip:
        raise HTTPException(status_code=404, detail="Belum ada transkrip untuk rapat ini")
    transkrip.teks = payload.teks
    db.commit()
    return schemas.TranskripOut.model_validate(transkrip)


@router.get("/{rapat_id}/transkripsi", response_model=schemas.TranskripOut)
def get_transkripsi(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    transkrip = (db.query(models.MeetingTranskrip)
                 .filter(models.MeetingTranskrip.meeting_id == rapat_id)
                 .order_by(models.MeetingTranskrip.id.desc()).first())
    if not transkrip:
        raise HTTPException(status_code=404, detail="Belum ada transkrip untuk rapat ini")
    return schemas.TranskripOut.model_validate(transkrip)


# ============================================================
#  NOTULA
# ============================================================
def _get_or_create_notula(db: Session, meeting_id: int) -> models.MeetingNotula:
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == meeting_id).first()
    if not notula:
        notula = models.MeetingNotula(meeting_id=meeting_id, status=models.StatusNotulaEnum.kosong)
        db.add(notula)
        db.commit()
        db.refresh(notula)
    return notula


def _run_notula(meeting_id: int):
    db = SessionLocal()
    try:
        meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
        if not meeting:
            return
        notula = _get_or_create_notula(db, meeting_id)
        transkrip = (db.query(models.MeetingTranskrip)
                     .filter(models.MeetingTranskrip.meeting_id == meeting_id,
                             models.MeetingTranskrip.status == models.StatusTranskripEnum.siap)
                     .order_by(models.MeetingTranskrip.id.desc()).first())
        try:
            if not transkrip or not transkrip.teks:
                raise RuntimeError("Belum ada transkrip siap untuk diringkas")
            pimpinan = db.query(models.User).filter(models.User.id == meeting.pimpinan_id).first() \
                if meeting.pimpinan_id else None
            result = summarize_transcript(transkrip.teks, {
                "judul_rapat": meeting.judul_rapat,
                "tanggal": meeting.tanggal,
                "pimpinan": pimpinan.nama if pimpinan else "",
                "peserta": _peserta_nama_gabungan(db, meeting_id),
                "agenda": meeting.agenda or "",
                # Ekstraksi teks dokumen (meeting_dokumen) sebagai konteks LLM
                # menyusul di Fase 2/3 bersamaan dengan UI tab Dokumen.
                "materi_rapat": "",
                "catatan_notulis": meeting.catatan_notulis or "",
            }, struktur="ringkas")
            notula.ringkasan = json.dumps(result["ringkasan"], ensure_ascii=False)
            notula.pertanyaan_jawaban = json.dumps(result["pertanyaan_jawaban"], ensure_ascii=False)
            if not notula.pendahuluan:
                notula.pendahuluan = build_pendahuluan_text(meeting, pimpinan)
            notula.sumber = models.SumberNotulaEnum.llm
            notula.status = models.StatusNotulaEnum.draft_ai
            notula.diperbarui_pada = now_wib()
            db.commit()
            transisi(db, meeting, "notula_berhasil", actor=None, catatan="Draft notula dibuat otomatis oleh AI")
        except Exception as e:
            db.rollback()
            notula = _get_or_create_notula(db, meeting_id)
            transisi(db, meeting, "notula_gagal", actor=None, catatan=f"Generate notula gagal: {e}")
    finally:
        db.close()


@router.post("/{rapat_id}/notula/generate", response_model=schemas.RapatOut)
def generate_notula(rapat_id: int, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    ada_transkrip = db.query(models.MeetingTranskrip).filter(
        models.MeetingTranskrip.meeting_id == rapat_id,
        models.MeetingTranskrip.status == models.StatusTranskripEnum.siap,
    ).count() > 0
    if not ada_transkrip:
        raise HTTPException(status_code=400, detail="Belum ada transkrip siap untuk diringkas")
    transisi(db, meeting, "mulai_notula", actor=current_user)
    threading.Thread(target=_run_notula, args=(rapat_id,), daemon=True).start()
    return _to_rapat_out(db, meeting)


@router.post("/{rapat_id}/notula/manual", response_model=schemas.NotulaOut)
def notula_manual(rapat_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    pastikan_status(meeting, S.selesai)
    notula = _get_or_create_notula(db, rapat_id)
    notula.status = models.StatusNotulaEnum.draft_manual
    notula.sumber = models.SumberNotulaEnum.manual
    db.commit()
    transisi(db, meeting, "notula_manual", actor=current_user)
    return _to_notula_out(db, notula)


@router.get("/{rapat_id}/notula", response_model=schemas.NotulaOut)
def get_notula(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if not notula:
        if meeting.lifecycle_status in (S.draft, S.dijadwalkan, S.berlangsung):
            raise HTTPException(status_code=404, detail="Notula belum tersedia - rapat belum diakhiri")
        # Rapat sudah SELESAI (atau lebih lanjut) tapi belum ada baris notula -
        # buat form kosong langsung, bukan menampilkan gerbang pilihan AI/Manual.
        notula = _get_or_create_notula(db, rapat_id)
    # pendahuluan di-seed begitu rapat sudah SELESAI+ meski baris notula sudah
    # ada sebelumnya (mis. dibuat oleh _run_notula yang gagal sebelum sempat
    # mengisi pendahuluan) - bukan hanya saat baris baru dibuat di atas.
    if not notula.pendahuluan and meeting.lifecycle_status not in (S.draft, S.dijadwalkan, S.berlangsung):
        pimpinan = db.query(models.User).filter(models.User.id == meeting.pimpinan_id).first() \
            if meeting.pimpinan_id else None
        notula.pendahuluan = build_pendahuluan_text(meeting, pimpinan)
        db.commit()
    return _to_notula_out(db, notula)


@router.patch("/{rapat_id}/notula", response_model=schemas.NotulaOut)
def edit_notula(rapat_id: int, payload: schemas.NotulaUpdate, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    """Autosave - boleh selama SELESAI atau REVIEW (form notula selalu bisa
    diedit begitu rapat diakhiri; di FINAL harus 'Buka Kembali' dulu)."""
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    pastikan_status(meeting, S.selesai, S.review)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if not notula:
        notula = _get_or_create_notula(db, rapat_id)
    data = payload.model_dump(exclude_unset=True)
    if "pendahuluan" in data:
        notula.pendahuluan = data["pendahuluan"]
    if "ringkasan" in data and data["ringkasan"] is not None:
        notula.ringkasan = json.dumps(data["ringkasan"], ensure_ascii=False)
    if "pertanyaan_jawaban" in data and data["pertanyaan_jawaban"] is not None:
        notula.pertanyaan_jawaban = json.dumps(data["pertanyaan_jawaban"], ensure_ascii=False)
    if "keputusan" in data and data["keputusan"] is not None:
        notula.keputusan = json.dumps(data["keputusan"], ensure_ascii=False)
    if "catatan_tambahan" in data:
        notula.catatan_tambahan = data["catatan_tambahan"]
    if notula.sumber == models.SumberNotulaEnum.llm:
        notula.sumber = models.SumberNotulaEnum.campuran
    # Item 39: menyimpan (bukan finalisasi) menandai notula sedang "Proses" -
    # lihat notulaStatusSimpleLabel() di frontend, yang menampilkan Proses
    # untuk status apapun selain kosong/final.
    if notula.status == models.StatusNotulaEnum.kosong:
        notula.status = models.StatusNotulaEnum.draft_manual
    notula.diperbarui_pada = now_wib()
    db.commit()
    return _to_notula_out(db, notula)


@router.post("/{rapat_id}/notula/tindak-lanjut", response_model=schemas.TindakLanjutOut)
def tambah_tindak_lanjut(rapat_id: int, payload: schemas.TindakLanjutIn, db: Session = Depends(get_db),
                          current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    notula = _get_or_create_notula(db, rapat_id)
    try:
        status_enum = models.ActionStatusEnum(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="status tidak valid")
    item = models.MeetingTindakLanjut(
        notula_id=notula.id, deskripsi=payload.deskripsi,
        penanggung_jawab=payload.penanggung_jawab, deadline=payload.deadline, status=status_enum,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return schemas.TindakLanjutOut.model_validate(item)


@router.patch("/{rapat_id}/notula/tindak-lanjut/{item_id}", response_model=schemas.TindakLanjutOut)
def edit_tindak_lanjut(rapat_id: int, item_id: int, payload: schemas.TindakLanjutIn, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    item = db.query(models.MeetingTindakLanjut).filter(
        models.MeetingTindakLanjut.id == item_id,
        models.MeetingTindakLanjut.notula_id == notula.id if notula else -1,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tindak lanjut tidak ditemukan")
    try:
        item.status = models.ActionStatusEnum(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="status tidak valid")
    item.deskripsi = payload.deskripsi
    item.penanggung_jawab = payload.penanggung_jawab
    item.deadline = payload.deadline
    db.commit()
    return schemas.TindakLanjutOut.model_validate(item)


@router.delete("/{rapat_id}/notula/tindak-lanjut/{item_id}")
def hapus_tindak_lanjut(rapat_id: int, item_id: int, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    tolak_jika_diarsipkan(meeting)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    item = db.query(models.MeetingTindakLanjut).filter(
        models.MeetingTindakLanjut.id == item_id,
        models.MeetingTindakLanjut.notula_id == notula.id if notula else -1,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tindak lanjut tidak ditemukan")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/{rapat_id}/notula/finalisasi", response_model=schemas.RapatOut)
def finalisasi_notula(rapat_id: int, db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):
    """Finalisasi notula langsung mengarsipkan rapat (satu langkah) - tidak
    ada lagi status FINAL antara/tombol "Arsipkan" terpisah, lihat
    rapat_lifecycle._TRANSITIONS."""
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if not notula or (json.loads(notula.ringkasan or "[]") == [] and json.loads(notula.pertanyaan_jawaban or "[]") == []):
        raise HTTPException(status_code=400, detail="Isi pembahasan atau tanya-jawab terlebih dahulu sebelum finalisasi")

    transisi(db, meeting, "finalisasi", actor=current_user)
    notula.status = models.StatusNotulaEnum.final
    notula.versi += 1
    notula.difinalisasi_oleh = current_user.id
    notula.difinalisasi_pada = now_wib()
    db.add(models.MeetingNotulaRiwayat(
        notula_id=notula.id, versi=notula.versi, snapshot=_snapshot_notula(notula),
        aksi=models.AksiRiwayatNotulaEnum.finalisasi, diubah_oleh=current_user.id,
    ))
    db.commit()
    return _to_rapat_out(db, meeting)


@router.post("/{rapat_id}/buka-arsip", response_model=schemas.RapatOut)
def buka_arsip_rapat(rapat_id: int, payload: schemas.AlasanRequest, db: Session = Depends(get_db),
                      current_user: models.User = Depends(require_roles("admin"))):
    """Satu-satunya jalan merevisi notula yang sudah final/diarsipkan - langsung
    ke REVIEW (bukan lagi dua langkah "Buka Arsip" + "Buka Kembali untuk
    Revisi" dengan alasan masing-masing)."""
    meeting = _get_rapat_or_404(db, rapat_id)
    transisi(db, meeting, "buka_arsip", actor=current_user, catatan=payload.alasan)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if notula:
        notula.status = models.StatusNotulaEnum.review
        db.add(models.MeetingNotulaRiwayat(
            notula_id=notula.id, versi=notula.versi, snapshot=_snapshot_notula(notula),
            aksi=models.AksiRiwayatNotulaEnum.buka_kembali, alasan=payload.alasan, diubah_oleh=current_user.id,
        ))
        db.commit()
    return _to_rapat_out(db, meeting)


# ============================================================
#  RIWAYAT STATUS (audit trail)
# ============================================================
@router.get("/{rapat_id}/riwayat-status", response_model=List[schemas.StatusLogOut])
def riwayat_status(rapat_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _get_rapat_or_404(db, rapat_id)
    rows = (db.query(models.MeetingStatusLog)
            .filter(models.MeetingStatusLog.meeting_id == rapat_id)
            .order_by(models.MeetingStatusLog.diubah_pada).all())
    hasil = []
    for r in rows:
        nama = None
        if r.diubah_oleh:
            u = db.query(models.User).filter(models.User.id == r.diubah_oleh).first()
            nama = u.nama if u else None
        hasil.append(schemas.StatusLogOut(
            status_dari=r.status_dari, status_ke=r.status_ke, diubah_oleh=nama,
            diubah_pada=r.diubah_pada, catatan=r.catatan,
        ))
    return hasil


# ============================================================
#  EXPORT - Word & PDF
# ============================================================
def _build_export_docx(db: Session, rapat_id: int) -> tuple:
    """Menyusun dokumen Word notula untuk sebuah rapat dari alur baru.
    Setara `_build_export_docx` di main.py, tapi membaca dari tabel
    relasional baru (MeetingPeserta/MeetingNotula/MeetingDokumen) alih-alih
    peserta_ids/Summary/Documentation lama."""
    meeting = _get_rapat_or_404(db, rapat_id)
    notula = db.query(models.MeetingNotula).filter(models.MeetingNotula.meeting_id == rapat_id).first()
    if not notula or (json.loads(notula.ringkasan or "[]") == [] and json.loads(notula.pertanyaan_jawaban or "[]") == []):
        raise HTTPException(status_code=400, detail="Notula belum diisi, tidak ada yang bisa diekspor")

    peserta_rows = db.query(models.MeetingPeserta).filter(models.MeetingPeserta.meeting_id == rapat_id).all()
    peserta_list = []
    for p in peserta_rows:
        if p.user_id and p.user:
            peserta_list.append(SimpleNamespace(nama=p.user.nama, jabatan=p.user.jabatan or "-"))
        else:
            peserta_list.append(SimpleNamespace(
                nama=p.nama_manual or "-", jabatan=p.jabatan_manual or p.instansi_manual or "-",
            ))
    dokumentasi = db.query(models.MeetingDokumen).filter(
        models.MeetingDokumen.meeting_id == rapat_id,
        models.MeetingDokumen.jenis == models.JenisDokumenEnum.dokumentasi,
        models.MeetingDokumen.status == models.StatusDokumenEnum.aktif,
    ).all()

    pimpinan = db.query(models.User).filter(models.User.id == meeting.pimpinan_id).first() if meeting.pimpinan_id else None
    notulis = db.query(models.User).filter(models.User.id == meeting.notulis_id).first() if meeting.notulis_id else None
    kepala = _get_kepala_bps(db)

    output_path = settings.EXPORT_DIR / f"notula_{rapat_id}_{uuid.uuid4().hex[:8]}.docx"
    try:
        build_notulensi_docx(
            meeting=meeting,
            transcript_text="",  # Lampiran transkripsi tidak ditampilkan di export Sistem B (permintaan pengguna)
            ringkasan=json.loads(notula.ringkasan or "[]"),
            keputusan=json.loads(notula.keputusan or "[]"),
            tindak_lanjut=[{
                "deskripsi": t.deskripsi, "penanggung_jawab": t.penanggung_jawab,
                "deadline": t.deadline, "status": t.status.value,
            } for t in notula.tindak_lanjut],
            peserta_list=peserta_list,
            pimpinan=pimpinan, notulis=notulis, kepala=kepala,
            dokumentasi_files=[{"path": settings.DOKUMEN_DIR / d.file_path, "keterangan": None} for d in dokumentasi],
            output_path=output_path,
            struktur="ringkas",
            pendahuluan_text=notula.pendahuluan,
            pertanyaan_jawaban=json.loads(notula.pertanyaan_jawaban or "[]"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyusun dokumen Word: {e}")
    return meeting, output_path


@router.get("/{rapat_id}/export/docx")
def export_docx(rapat_id: int, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    meeting, output_path = _build_export_docx(db, rapat_id)
    return FileResponse(
        path=output_path,
        filename=f"Notula - {meeting.judul_rapat}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{rapat_id}/export/pdf")
def export_pdf(rapat_id: int, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    meeting, docx_path = _build_export_docx(db, rapat_id)
    try:
        pdf_path = convert_docx_to_pdf(docx_path, settings.EXPORT_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FileResponse(
        path=pdf_path,
        filename=f"Notula - {meeting.judul_rapat}.pdf",
        media_type="application/pdf",
    )
