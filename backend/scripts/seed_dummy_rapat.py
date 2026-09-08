"""Isi rapat contoh (dummy) Januari-September 2026 supaya grafik Dashboard &
Kalender Kegiatan punya data representatif.

Jalankan sekali dari folder backend:
    ./venv/Scripts/python.exe -m scripts.seed_dummy_rapat        (atau python scripts/seed_dummy_rapat.py)

Idempoten: rapat dummy diberi prefiks judul "[dummy] " - kalau sudah ada, skip.
Untuk menghapus lagi: hapus baris meetings yang judul_rapat LIKE '[dummy]%'.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal          # noqa: E402
from app import models                          # noqa: E402
from app.routers.rapat import _users_in_tim, TIM_LIST  # noqa: E402
from app.utils.tz import now_wib                # noqa: E402

S = models.MeetingLifecycleStatus
PREFIX = "[dummy] "

# Topik contoh per tim (dipakai untuk variasi judul).
TOPIK = {
    "Umum": ["Rapat Koordinasi Kepegawaian", "Evaluasi Anggaran", "Rapat Persiapan Audit", "Koordinasi Layanan Umum"],
    "IPDS": ["Rapat Pengembangan Aplikasi", "Evaluasi Diseminasi Data", "Koordinasi Web & Infografis", "Rapat Metadata"],
    "Produksi": ["Rapat Ubinan Padi", "Evaluasi Survei Industri", "Koordinasi Statistik Pertanian", "Rapat Sensus Ekonomi"],
    "Distribusi": ["Rapat Survei Harga Konsumen", "Evaluasi Statistik Distribusi", "Koordinasi Pariwisata", "Rapat Transportasi"],
    "Neraca": ["Rapat PDRB Triwulanan", "Evaluasi Neraca Produksi", "Koordinasi Nilai Tambah", "Rapat Tabel I-O"],
    "Sosial": ["Rapat Susenas", "Evaluasi Sakernas", "Koordinasi Statistik Pendidikan", "Rapat Kemiskinan"],
    "": ["Rapat Pimpinan", "Rapat Bulanan BPS Kabupaten", "Sosialisasi Kegiatan Lintas Tim", "Rapat Evaluasi Kinerja"],
}

# Distribusi status per bulan: makin lampau -> makin banyak "selesai/arsip".
def _status_for(month: int) -> "S":
    now_month = now_wib().month
    if month < now_month - 1:
        return random.choice([S.selesai, S.selesai, S.diarsipkan, S.review, S.final])
    if month == now_month:
        return random.choice([S.dijadwalkan, S.berlangsung, S.selesai])
    if month > now_month:
        return S.dijadwalkan
    return random.choice([S.selesai, S.review, S.dijadwalkan])


def main():
    db = SessionLocal()
    try:
        if db.query(models.Meeting).filter(models.Meeting.judul_rapat.like(f"{PREFIX}%")).count():
            print("[seed] rapat dummy sudah ada - tidak menambah lagi.")
            return

        admin = db.query(models.User).filter(models.User.role == models.RoleEnum.admin).first()
        actor_id = admin.id if admin else None
        pegawai = db.query(models.User).filter(models.User.role == models.RoleEnum.pegawai).order_by(models.User.urutan).all()
        if not pegawai:
            print("[seed] belum ada pegawai - jalankan aplikasi dulu agar seed pegawai berjalan.")
            return

        random.seed(20260101)
        tim_pool = TIM_LIST + ["", "", ""]   # ~1/3 rapat tanpa tim
        dibuat = 0

        for month in range(1, 10):  # Januari..September
            for _ in range(random.randint(3, 5)):
                tim = random.choice(tim_pool)
                day = random.randint(1, 27)
                tanggal = f"2026-{month:02d}-{day:02d}"
                jam = random.choice(["08:30", "09:00", "10:00", "13:00", "14:00"])
                jam_selesai = f"{int(jam[:2]) + 2:02d}{jam[2:]}"
                judul = PREFIX + random.choice(TOPIK[tim])

                anggota = _users_in_tim(db, tim) if tim else random.sample(pegawai, k=min(8, len(pegawai)))
                if not anggota:
                    anggota = random.sample(pegawai, k=min(6, len(pegawai)))
                anggota = anggota[:random.randint(3, 8)]
                pimpinan = random.choice(anggota) if anggota else None
                notulis = random.choice([a for a in anggota if a is not pimpinan] or anggota) if anggota else None

                status = _status_for(month)
                m = models.Meeting(
                    unit_kerja="BPS Kabupaten Sanggau", tim=(tim or None),
                    judul_rapat=judul, tanggal=tanggal,
                    waktu_mulai=jam, waktu_selesai=jam_selesai,
                    lokasi=random.choice(["Ruang Rapat Lantai 1", "Ruang Rapat Lantai 2", "Aula BPS", "Ruang Kepala"]),
                    agenda=f"Pembahasan {judul[len(PREFIX):].lower()}",
                    pimpinan_id=pimpinan.id if pimpinan else None,
                    notulis_id=notulis.id if notulis else actor_id,
                    lifecycle_status=status, user_id=actor_id,
                )
                db.add(m)
                db.flush()
                db.add(models.MeetingStatusLog(
                    meeting_id=m.id, status_dari=None, status_ke=S.draft.value,
                    diubah_oleh=actor_id, catatan="Rapat dummy dibuat",
                ))
                if status != S.draft:
                    db.add(models.MeetingStatusLog(
                        meeting_id=m.id, status_dari=S.draft.value, status_ke=status.value,
                        diubah_oleh=actor_id, catatan="Status awal dummy",
                    ))
                for u in anggota:
                    p = models.MeetingPeserta(
                        meeting_id=m.id, user_id=u.id,
                        peran=models.PeranPesertaEnum.undangan,
                        sumber=models.SumberPesertaEnum.diundang,
                        ditambahkan_oleh=actor_id,
                    )
                    db.add(p)
                    db.flush()
                    hadir = models.StatusKehadiranEnum.hadir if status in (S.selesai, S.review, S.final, S.diarsipkan, S.berlangsung) and random.random() > 0.15 else models.StatusKehadiranEnum.tidak_hadir
                    db.add(models.MeetingKehadiran(
                        peserta_id=p.id, status_kehadiran=hadir,
                        waktu_hadir=now_wib(), dicatat_oleh=actor_id,
                    ))
                dibuat += 1

        db.commit()
        print(f"[seed] {dibuat} rapat dummy dibuat (Jan-Sep 2026).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
