"""Surat Undangan - langkah "Pratinjau" & "Blast WhatsApp" pada wizard menu
"Rapat". TERIKAT ke satu rapat: field surat default terisi dari data rapat, dan
daftar penerima + nomor WhatsApp diambil otomatis dari peserta undangan rapat
(MeetingPeserta peran=undangan -> User.no_whatsapp) - tidak ada input manual.

Pola build dokumen sama dengan ekspor notula: isi undangan_template.docx ->
konversi PDF (lihat services/docx_export.build_undangan_from_template &
services/pdf_export.convert_docx_to_pdf). Blast teks polos lewat gateway
whacenter (services/whatsapp.kirim_teks_whacenter - TIDAK RESMI, uji coba saja).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from .. import models, schemas
from ..auth import get_current_user, assert_can_write_meeting
from ..config import settings
from ..database import get_db
from ..services.docx_export import build_undangan_from_template, UNDANGAN_TEMPLATE_PATH
from ..services.pdf_export import convert_docx_to_pdf
from ..services.whatsapp import kirim_teks_whacenter
from ..utils.indo_date import format_tanggal_lengkap, format_tanggal_singkat
from ..utils.tz import now_wib
from .rapat import _get_rapat_or_404
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/rapat", tags=["undangan"])


def _peserta_undangan(db: Session, rapat_id: int):
    """Peserta rapat untuk surat undangan & blast - mencakup yang ditambahkan
    lewat "Pilih Rapat Tim" (peran=undangan) MAUPUN tambahan manual (peran default
    'peserta'), TAPI: (1) buang walk-in (bukan "diundang"), (2) DEDUP per orang
    supaya jumlah & blast tidak dobel saat 1 orang terdaftar di >1 baris."""
    rows = (db.query(models.MeetingPeserta)
            .filter(models.MeetingPeserta.meeting_id == rapat_id,
                    models.MeetingPeserta.sumber != models.SumberPesertaEnum.walk_in)
            .order_by(models.MeetingPeserta.id).all())
    out, seen = [], set()
    for p in rows:
        key = ("u", p.user_id) if p.user_id else ("n", (p.nama_manual or "").strip().lower())
        if key in seen or key == ("n", ""):
            continue
        seen.add(key)
        out.append(p)
    return out


def _peran_rapat(meeting: models.Meeting, p: models.MeetingPeserta) -> str:
    """Peran orang ini terhadap rapat - dipakai untuk keterangan di teks blast WA."""
    if p.user_id and meeting.pimpinan_id and p.user_id == meeting.pimpinan_id:
        return "pimpinan"
    if p.user_id and meeting.notulis_id and p.user_id == meeting.notulis_id:
        return "notulis"
    return "peserta"


_PERAN_WA_NOTE = {
    "pimpinan": "\n\n_Bapak/Ibu tercatat sebagai *Pimpinan Rapat* pada kegiatan ini._",
    "notulis": "\n\n_Bapak/Ibu ditugaskan sebagai *Notulis* pada rapat ini._",
    "peserta": "",
}


def _peserta_nama_jabatan(p: models.MeetingPeserta):
    if p.user_id and p.user:
        return p.user.nama, (p.user.jabatan or "-"), (p.user.no_whatsapp or "").strip()
    return (p.nama_manual or "-"), (p.jabatan_manual or p.instansi_manual or "-"), ""


def _default_fields(meeting: models.Meeting) -> dict:
    waktu = meeting.waktu_mulai or ""
    if meeting.waktu_selesai:
        waktu = f"{waktu} - {meeting.waktu_selesai}".strip(" -")
    if waktu:
        waktu = f"{waktu} WIB"
    return {
        "nomor_surat": "-",
        "sifat": "Biasa",
        "lampiran": "1 (satu) berkas",
        "hal": meeting.judul_rapat or "Rapat",
        "kota": (meeting.unit_kerja or settings.UNIT_KERJA_DEFAULT).split(" ")[-1] or "Sanggau",
        "tanggal_surat": format_tanggal_singkat(now_wib().strftime("%Y-%m-%d")),
        "dasar": (meeting.agenda or "koordinasi lebih lanjut").strip(),
        "hari_tanggal": format_tanggal_lengkap(meeting.tanggal) if meeting.tanggal else "-",
        "waktu": waktu or "-",
        "tempat": meeting.lokasi or "-",
        "agenda": meeting.agenda or "-",
    }


def _slug(teks: str) -> str:
    aman = "".join(c if c.isalnum() or c in " -_" else "" for c in (teks or "")).strip()
    return (aman or "Undangan")[:80]


def _build_docx(db: Session, meeting: models.Meeting, fields: dict):
    if not UNDANGAN_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Template undangan tidak ada di server: {UNDANGAN_TEMPLATE_PATH}")
    penerima = []
    for p in _peserta_undangan(db, meeting.id):
        nama, jabatan, _wa = _peserta_nama_jabatan(p)
        penerima.append({"nama": nama, "jabatan": jabatan})
    out = settings.EXPORT_DIR / f"undangan_{meeting.id}_{uuid.uuid4().hex[:8]}.docx"
    try:
        build_undangan_from_template(fields, penerima, out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyusun dokumen undangan: {e}")
    return out


@router.get("/{rapat_id}/undangan/data")
def undangan_data(rapat_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    """Field surat (default dari data rapat) + ringkasan penerima untuk langkah
    Pratinjau/Blast di frontend."""
    meeting = _get_rapat_or_404(db, rapat_id)
    penerima = []
    for p in _peserta_undangan(db, rapat_id):
        nama, jabatan, wa = _peserta_nama_jabatan(p)
        penerima.append({"nama": nama, "jabatan": jabatan, "punya_wa": bool(wa),
                         "peran_rapat": _peran_rapat(meeting, p)})
    return {"fields": _default_fields(meeting), "penerima": penerima,
            "jumlah": len(penerima), "whacenter_ready": settings.WHACENTER_READY}


@router.post("/{rapat_id}/undangan/pratinjau")
def undangan_pratinjau(rapat_id: int, payload: schemas.UndanganPratinjauIn,
                        db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    docx_path = _build_docx(db, meeting, payload.model_dump())
    try:
        pdf_path = convert_docx_to_pdf(docx_path, settings.EXPORT_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FileResponse(path=pdf_path, filename=f"{_slug(payload.hal)}.pdf",
                        media_type="application/pdf")


@router.post("/{rapat_id}/undangan/unduh")
def undangan_unduh(rapat_id: int, payload: schemas.UndanganPratinjauIn,
                    format: str = Query("docx", pattern="^(docx|pdf)$"),
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    docx_path = _build_docx(db, meeting, payload.model_dump())
    if format == "docx":
        return FileResponse(
            path=docx_path, filename=f"{_slug(payload.hal)}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    try:
        pdf_path = convert_docx_to_pdf(docx_path, settings.EXPORT_DIR)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return FileResponse(path=pdf_path, filename=f"{_slug(payload.hal)}.pdf",
                        media_type="application/pdf")


@router.post("/{rapat_id}/undangan/blast-wa")
def undangan_blast_wa(rapat_id: int, payload: schemas.UndanganBlastIn,
                       db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):
    """Kirim teks undangan (polos, tanpa lampiran) ke tiap peserta undangan yang
    punya nomor WA (User.no_whatsapp). Yang tanpa nomor dilaporkan di
    `tanpa_nomor`, tidak menggagalkan yang lain."""
    meeting = _get_rapat_or_404(db, rapat_id)
    assert_can_write_meeting(current_user, meeting)
    pesan = (payload.pesan or "").strip()
    if not pesan:
        raise HTTPException(status_code=400, detail="Teks pesan WhatsApp kosong.")
    peserta = _peserta_undangan(db, rapat_id)
    if not peserta:
        raise HTTPException(status_code=404, detail="Rapat ini belum punya peserta. Tambahkan peserta di langkah Peserta.")
    if not settings.WHACENTER_READY:
        raise HTTPException(
            status_code=400,
            detail="Blast WhatsApp belum aktif: isi WHACENTER_DEVICE_ID di .env server (gateway whacenter, lihat README).",
        )
    hasil, tanpa_nomor = [], []
    for p in peserta:
        nama, _jab, wa = _peserta_nama_jabatan(p)
        if not wa:
            tanpa_nomor.append(nama)
            continue
        peran = _peran_rapat(meeting, p)
        r = kirim_teks_whacenter(wa, pesan + _PERAN_WA_NOTE.get(peran, ""))
        hasil.append({"nama": nama, "nomor": wa, "peran_rapat": peran, **r})
    return {"hasil": hasil, "terkirim": sum(1 for h in hasil if h.get("ok")),
            "tanpa_nomor": tanpa_nomor}
