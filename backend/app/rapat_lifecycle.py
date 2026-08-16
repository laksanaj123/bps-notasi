"""State machine terpusat untuk siklus hidup rapat baru
(lihat RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md §2 & §2.3).

Aturan: tidak ada kode di luar modul ini yang boleh menulis
`meeting.lifecycle_status = ...` secara langsung. Setiap endpoint yang
memicu perpindahan status WAJIB memanggil `transisi()` supaya validitas
graf status terjaga dan `MeetingStatusLog` selalu tercatat.

Guard yang butuh data di luar status itu sendiri (mis. "finalisasi hanya
boleh kalau ringkasan/keputusan terisi", atau pengecekan role) SENGAJA
tidak ditaruh di sini - modul ini murni menjaga validitas graf transisi.
Guard bisnis semacam itu dicek oleh endpoint di routers/rapat.py sebelum
memanggil transisi(), supaya modul ini tidak perlu tahu tentang notula,
role pengguna, dsb.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models

S = models.MeetingLifecycleStatus

# aksi -> {status_asal: status_tujuan}
# "mulai_transkripsi"/"mulai_notula" sama-sama menuju DIPROSES (dipakai
# bergantian, tidak paralel - lihat §1.1 rancangan: transkripsi dan
# generate notula adalah dua langkah berurutan, bukan dua job bersamaan).
_TRANSITIONS: dict[str, dict[models.MeetingLifecycleStatus, models.MeetingLifecycleStatus]] = {
    "jadwalkan":           {S.draft: S.dijadwalkan},
    "mulai":               {S.draft: S.berlangsung, S.dijadwalkan: S.berlangsung},
    "batalkan":            {S.draft: S.dibatalkan, S.dijadwalkan: S.dibatalkan, S.berlangsung: S.dibatalkan},
    "akhiri":              {S.berlangsung: S.selesai},
    # Transkripsi tidak lagi menunggu rapat diakhiri (item 38) - boleh
    # dimulai selagi BERLANGSUNG asalkan sudah ada segmen rekaman siap
    # (dicek di routers/rapat.py). Saat dipicu dari BERLANGSUNG, rapat
    # SENGAJA tidak dipindah ke DIPROSES (itu berarti "rapat sedang
    # diproses AI pasca-selesai", bukan cocok untuk rapat yang masih
    # berjalan) - proses_transkripsi() di routers/rapat.py melewati
    # transisi() ini sepenuhnya untuk kasus BERLANGSUNG, progres transkrip
    # cukup dilacak lewat MeetingTranskrip.status sendiri.
    "mulai_transkripsi":   {S.selesai: S.diproses},
    "transkripsi_selesai": {S.diproses: S.selesai},   # baik berhasil maupun gagal - lihat modul routers/rapat.py
    "mulai_notula":        {S.selesai: S.diproses},
    "notula_gagal":        {S.diproses: S.selesai},
    "notula_manual":       {S.selesai: S.review},
    "notula_berhasil":     {S.diproses: S.review},
    # alur Buat Rapat baru mengizinkan finalisasi langsung dari SELESAI (form
    # notula selalu bisa diedit begitu rapat selesai, tidak wajib lewat REVIEW).
    # Finalisasi langsung mengarsipkan rapat (tidak ada lagi status FINAL
    # transisi/tombol "Arsipkan" terpisah - lihat routers/rapat.py
    # finalisasi_notula()). Status FINAL dipertahankan di enum untuk data lama
    # saja, tidak lagi jadi tujuan transisi manapun.
    "finalisasi":          {S.review: S.diarsipkan, S.selesai: S.diarsipkan},
    # Satu-satunya jalan membuka rapat yang sudah diarsipkan - langsung ke
    # REVIEW supaya notula bisa direvisi tanpa langkah "Buka Kembali" terpisah
    # (dan tanpa alasan tambahan di luar alasan buka-arsip ini sendiri).
    "buka_arsip":          {S.diarsipkan: S.review},
}


def transisi(
    db: Session,
    meeting: models.Meeting,
    aksi: str,
    actor: Optional[models.User] = None,
    catatan: Optional[str] = None,
) -> models.Meeting:
    """Validasi & terapkan satu perpindahan status, catat ke meeting_status_log.

    `actor=None` dipakai untuk transisi yang dipicu sistem (mis. worker
    background transkripsi/LLM), bukan aksi pengguna langsung.
    """
    if meeting.lifecycle_status is None:
        raise HTTPException(
            status_code=400,
            detail="Rapat ini belum masuk alur baru (dibuat lewat wizard lama, tidak punya lifecycle_status).",
        )

    current = meeting.lifecycle_status
    mapping = _TRANSITIONS.get(aksi)
    if not mapping or current not in mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Tidak bisa melakukan '{aksi}' pada rapat berstatus '{current.value}'.",
        )

    target = mapping[current]
    meeting.lifecycle_status = target
    db.add(models.MeetingStatusLog(
        meeting_id=meeting.id,
        status_dari=current.value,
        status_ke=target.value,
        diubah_oleh=actor.id if actor else None,
        catatan=catatan,
    ))
    db.commit()
    db.refresh(meeting)
    return meeting


def pastikan_status(meeting: models.Meeting, *allowed: models.MeetingLifecycleStatus) -> None:
    """Guard untuk endpoint yang TIDAK mengubah status tapi hanya boleh
    jalan di status tertentu (mis. autosave notula hanya saat REVIEW)."""
    if meeting.lifecycle_status not in allowed:
        label = meeting.lifecycle_status.value if meeting.lifecycle_status else "-"
        raise HTTPException(status_code=400, detail=f"Aksi ini tidak tersedia pada status '{label}'.")


def tolak_jika_diarsipkan(meeting: models.Meeting) -> None:
    """Guard longgar dipakai endpoint yang boleh jalan di HAMPIR semua
    status (tambah peserta, upload dokumen, dst) - hanya DIARSIPKAN yang
    read-only penuh, sesuai prinsip "jangan kunci data opsional"."""
    if meeting.lifecycle_status == S.diarsipkan:
        raise HTTPException(
            status_code=400,
            detail="Rapat sudah diarsipkan dan bersifat baca-saja. Buka arsip terlebih dahulu untuk mengubahnya.",
        )
