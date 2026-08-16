import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, Boolean, LargeBinary
)
from sqlalchemy.orm import relationship
from .database import Base
from .utils.tz import now_wib


class RoleEnum(str, enum.Enum):
    admin = "admin"
    pegawai = "pegawai"


class StatusEnum(str, enum.Enum):
    menunggu = "menunggu"       # baru diunggah, belum diproses
    diproses = "diproses"       # sedang STT/LLM
    selesai = "selesai"         # sudah ada ringkasan
    gagal = "gagal"


class ActionStatusEnum(str, enum.Enum):
    pending = "Pending"
    in_progress = "In Progress"
    done = "Done"


# ============================================================
# Alur rapat baru (lihat RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md).
# Enum & tabel di bawah ini TERPISAH dari StatusEnum/Meeting lama di atas -
# keduanya hidup berdampingan, lihat catatan di rapat_lifecycle.py dan
# routers/rapat.py. Jangan gunakan MeetingLifecycleStatus untuk kolom
# `Meeting.status` (lama) atau sebaliknya.
# ============================================================

class MeetingLifecycleStatus(str, enum.Enum):
    draft = "draft"
    dijadwalkan = "dijadwalkan"
    berlangsung = "berlangsung"
    selesai = "selesai"
    diproses = "diproses"
    review = "review"
    final = "final"
    diarsipkan = "diarsipkan"
    dibatalkan = "dibatalkan"


class JenisMediaEnum(str, enum.Enum):
    offline = "offline"
    online = "online"
    hybrid = "hybrid"


class PeranPesertaEnum(str, enum.Enum):
    peserta = "peserta"
    undangan = "undangan"
    pemateri = "pemateri"


class SumberPesertaEnum(str, enum.Enum):
    diundang = "diundang"
    tambahan = "tambahan"
    walk_in = "walk_in"


class StatusKehadiranEnum(str, enum.Enum):
    """Disederhanakan jadi 2 nilai saja - status lama (belum_hadir/terlambat/izin)
    dipetakan lewat migrasi data di main.py._auto_migrate()."""
    hadir = "hadir"
    tidak_hadir = "tidak_hadir"


class JenisDokumenEnum(str, enum.Enum):
    materi = "materi"
    undangan = "undangan"
    dokumentasi = "dokumentasi"
    lainnya = "lainnya"


class StatusDokumenEnum(str, enum.Enum):
    aktif = "aktif"
    diganti = "diganti"
    dihapus = "dihapus"


class StatusRekamanEnum(str, enum.Enum):
    merekam = "merekam"
    dijeda = "dijeda"
    berhenti = "berhenti"
    mengunggah = "mengunggah"
    siap = "siap"
    gagal = "gagal"


class SumberTranskripEnum(str, enum.Enum):
    stt = "stt"
    manual = "manual"
    dokumen = "dokumen"


class StatusTranskripEnum(str, enum.Enum):
    menunggu = "menunggu"
    berjalan = "berjalan"
    siap = "siap"
    gagal = "gagal"


class StatusNotulaEnum(str, enum.Enum):
    kosong = "kosong"
    draft_ai = "draft_ai"
    draft_manual = "draft_manual"
    review = "review"
    final = "final"


class SumberNotulaEnum(str, enum.Enum):
    llm = "llm"
    manual = "manual"
    campuran = "campuran"


class AksiRiwayatNotulaEnum(str, enum.Enum):
    finalisasi = "finalisasi"
    buka_kembali = "buka_kembali"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(150), nullable=False)
    username = Column(String(80), unique=True, index=True, nullable=False)
    email = Column(String(150), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.pegawai)
    is_active = Column(Boolean, default=True)
    # --- Direktori pegawai, digabung dari tabel Pegawai lama (lihat
    # backend/scripts/migrate_pegawai_to_user.py). Setiap peserta rapat
    # kini adalah User berrole pegawai; jabatan dipakai untuk pilihan
    # Pimpinan Rapat/Notulis/Peserta dan cetak dokumen notula. ---
    jabatan = Column(String(200), nullable=True)
    urutan = Column(Integer, default=0)   # menjaga urutan tampilan sesuai daftar asli
    must_reset_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_wib)

    meetings = relationship("Meeting", back_populates="pembuat", foreign_keys="Meeting.user_id")


class AppSettings(Base):
    """Override provider AI (STT/LLM) yang bisa diubah lewat halaman
    Pengaturan tanpa restart server - baris tunggal, id selalu 1.
    Field yang NULL berarti "pakai default dari .env" (lihat config.py
    _load_settings_overrides()). Field non-NULL yang paling sering
    disentuh ada di sini; setelan lanjutan lain tetap lewat .env."""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    stt_provider = Column(String(20), nullable=True)
    llm_provider = Column(String(20), nullable=True)
    openai_api_key = Column(String(255), nullable=True)
    ollama_model = Column(String(100), nullable=True)
    whisper_local_model = Column(String(20), nullable=True)


class Pegawai(Base):
    """LEGACY - digantikan oleh User.jabatan (lihat komentar di atas & migrasi
    backend/scripts/migrate_pegawai_to_user.py). Tabel fisik dibiarkan ada
    sebagai jaring pengaman satu rilis, tapi tidak lagi dipakai kode manapun
    (endpoint /api/pegawai dan seed otomatis sudah dihapus)."""
    __tablename__ = "pegawai"

    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(200), nullable=False)
    jabatan = Column(String(200), nullable=False)
    urutan = Column(Integer, default=0)  # menjaga urutan tampilan sesuai daftar asli


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)

    # --- Kop / info rapat (mengikuti template-notule-kegiatan.md) ---
    unit_kerja = Column(String(200), default="BPS Kabupaten Sanggau")
    judul_rapat = Column(String(255), nullable=False)   # -> "Topik"
    tanggal = Column(String(20), nullable=False)        # YYYY-MM-DD
    waktu_mulai = Column(String(10))                    # "08:30"
    waktu_selesai = Column(String(10))                   # "10:00"
    lokasi = Column(String(150))                        # -> "Tempat"
    agenda = Column(Text)
    catatan_notulis = Column(Text)   # catatan kasar notulis, ikut dipertimbangkan AI saat meringkas

    # --- Pihak-pihak terkait (referensi ke users.id - lihat catatan merge
    # Pegawai->User di atas; notulis_id JUGA berfungsi sebagai penanda siapa
    # yang punya hak tulis atas rapat ini, lihat auth.py/routers/rapat.py) ---
    pimpinan_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notulis_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    peserta_ids = Column(Text, default="[]")   # JSON list[int] id users peserta (alur lama)

    # --- Berkas & status pemrosesan AI ---
    file_audio = Column(String(500))
    durasi_detik = Column(Float, default=0)
    status = Column(Enum(StatusEnum), default=StatusEnum.menunggu)
    progress = Column(Integer, default=0)            # 0-100, diperbarui background worker
    progress_stage = Column(String(255), default="")  # keterangan tahap yang sedang berjalan
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now_wib)

    # --- Alur rapat baru (nullable, tidak dipakai endpoint lama) ---
    # NULL berarti rapat ini belum pernah masuk alur baru (dibuat lewat wizard lama).
    lifecycle_status = Column(Enum(MeetingLifecycleStatus), nullable=True)
    jenis_media = Column(Enum(JenisMediaEnum), nullable=True)
    waktu_mulai_aktual = Column(DateTime, nullable=True)
    waktu_selesai_aktual = Column(DateTime, nullable=True)
    alasan_pembatalan = Column(Text, nullable=True)

    pembuat = relationship("User", back_populates="meetings", foreign_keys=[user_id])
    pimpinan = relationship("User", foreign_keys=[pimpinan_id])
    notulis = relationship("User", foreign_keys=[notulis_id])
    transcript = relationship("Transcript", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    archives = relationship("Archive", back_populates="meeting", cascade="all, delete-orphan")
    dokumentasi = relationship("Documentation", back_populates="meeting", cascade="all, delete-orphan")
    materi = relationship("MeetingMaterial", back_populates="meeting", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True)
    teks_transkripsi = Column(Text)
    created_at = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting", back_populates="transcript")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True)
    ringkasan = Column(Text)          # JSON string (list[str])
    keputusan = Column(Text)          # JSON string (list[str])
    updated_at = Column(DateTime, default=now_wib, onupdate=now_wib)

    meeting = relationship("Meeting", back_populates="summary")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    deskripsi = Column(String(500))
    penanggung_jawab = Column(String(150))
    deadline = Column(String(20))
    status = Column(Enum(ActionStatusEnum), default=ActionStatusEnum.pending)

    meeting = relationship("Meeting", back_populates="action_items")


class Archive(Base):
    __tablename__ = "archives"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    file_docx = Column(String(500))
    tanggal_export = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting", back_populates="archives")


class MeetingMaterial(Base):
    """Materi rapat (PDF/DOCX/PPTX/TXT) yang diunggah saat rapat dibuat.
    Teks hasil ekstraksi ikut dikirim ke LLM sebagai konteks tambahan,
    sama seperti catatan_notulis (lihat services/summarizer.py)."""
    __tablename__ = "meeting_materials"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    file_path = Column(String(500))     # path relatif terhadap MATERI_DIR
    nama_asli = Column(String(255))
    teks_terekstrak = Column(Text)
    uploaded_at = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting", back_populates="materi")


class Documentation(Base):
    """Bukti/dokumentasi kegiatan (foto) yang diunggah pengguna, akan disisipkan
    ke bagian 'Dokumentasi Kegiatan Rapat' pada dokumen notulensi hasil ekspor."""
    __tablename__ = "documentation"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    file_path = Column(String(500))     # path relatif terhadap BUKTI_DIR
    keterangan = Column(String(255), default="")
    uploaded_at = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting", back_populates="dokumentasi")


# ============================================================
# Tabel baru untuk alur rapat incremental (lihat
# RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md §14.2). Semua tabel di bawah ini
# baru (bukan pengganti tabel lama di atas) - dipakai eksklusif oleh
# routers/rapat.py, tidak disentuh endpoint /api/meetings lama.
# ============================================================

class MeetingPeserta(Base):
    """Daftar peserta rapat (direncanakan/diundang) - lihat MeetingKehadiran
    untuk siapa yang benar-benar hadir. Satu baris di sini boleh punya
    user_id (pegawai internal, sekarang = User berrole pegawai) ATAU data
    manual untuk peserta eksternal, tidak keduanya kosong."""
    __tablename__ = "meeting_peserta"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    nama_manual = Column(String(200), nullable=True)
    jabatan_manual = Column(String(200), nullable=True)
    instansi_manual = Column(String(200), nullable=True)
    peran = Column(Enum(PeranPesertaEnum), default=PeranPesertaEnum.peserta)
    sumber = Column(Enum(SumberPesertaEnum), default=SumberPesertaEnum.diundang)
    ditambahkan_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    ditambahkan_pada = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting")
    user = relationship("User", foreign_keys=[user_id])
    kehadiran = relationship("MeetingKehadiran", back_populates="peserta", uselist=False,
                              cascade="all, delete-orphan")


class MeetingKehadiran(Base):
    """Daftar hadir aktual, satu-ke-satu dengan MeetingPeserta. Dibuat saat
    peserta pertama kali dicentang/dicatat kehadirannya (tidak otomatis ada
    untuk setiap peserta terdaftar)."""
    __tablename__ = "meeting_kehadiran"

    id = Column(Integer, primary_key=True, index=True)
    peserta_id = Column(Integer, ForeignKey("meeting_peserta.id"), nullable=False, unique=True)
    status_kehadiran = Column(Enum(StatusKehadiranEnum), default=StatusKehadiranEnum.tidak_hadir)
    waktu_hadir = Column(DateTime, nullable=True)
    waktu_keluar = Column(DateTime, nullable=True)
    keterangan = Column(String(255), nullable=True)
    dicatat_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    dicatat_pada = Column(DateTime, default=now_wib)
    diedit_pasca_rapat = Column(Boolean, default=False)

    peserta = relationship("MeetingPeserta", back_populates="kehadiran")


class MeetingDokumen(Base):
    """Dokumen pendukung rapat (materi/undangan/dokumentasi/lainnya) -
    versi baru & berkategori dari MeetingMaterial/Documentation lama."""
    __tablename__ = "meeting_dokumen"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    nama_file = Column(String(255), nullable=False)
    jenis = Column(Enum(JenisDokumenEnum), default=JenisDokumenEnum.lainnya)
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    ukuran_bytes = Column(Integer, nullable=True)
    versi = Column(Integer, default=1)
    status = Column(Enum(StatusDokumenEnum), default=StatusDokumenEnum.aktif)
    diunggah_pasca_rapat = Column(Boolean, default=False)
    diunggah_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    diunggah_pada = Column(DateTime, default=now_wib)

    meeting = relationship("Meeting")


class MeetingRekaman(Base):
    """Satu segmen rekaman audio. Satu rapat boleh punya banyak segmen
    (rekaman terputus/berjeda/direkam ulang)."""
    __tablename__ = "meeting_rekaman"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    segmen_ke = Column(Integer, default=1)
    file_path = Column(String(500), nullable=True)   # NULL selagi masih merekam
    format = Column(String(10), nullable=True)
    durasi_detik = Column(Float, nullable=True)
    ukuran_bytes = Column(Integer, nullable=True)
    status = Column(Enum(StatusRekamanEnum), default=StatusRekamanEnum.merekam)
    pesan_error = Column(String(500), nullable=True)
    direkam_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    mulai_pada = Column(DateTime, default=now_wib)
    selesai_pada = Column(DateTime, nullable=True)

    meeting = relationship("Meeting")


class MeetingTranskrip(Base):
    """Transkrip rapat - hasil STT gabungan seluruh segmen rekaman siap,
    tempel manual, atau ekstraksi dokumen. Satu baris aktif per rapat
    (percobaan_ke naik setiap kali retry, baris lama tetap ada untuk audit)."""
    __tablename__ = "meeting_transkrip"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    rekaman_id = Column(Integer, ForeignKey("meeting_rekaman.id"), nullable=True)
    sumber = Column(Enum(SumberTranskripEnum), default=SumberTranskripEnum.stt)
    status = Column(Enum(StatusTranskripEnum), default=StatusTranskripEnum.menunggu)
    teks = Column(Text, nullable=True)
    bahasa = Column(String(10), nullable=True)
    model_stt = Column(String(50), nullable=True)
    pesan_error = Column(String(500), nullable=True)
    percobaan_ke = Column(Integer, default=1)
    mulai_pada = Column(DateTime, nullable=True)
    selesai_pada = Column(DateTime, nullable=True)

    meeting = relationship("Meeting")


class MeetingNotula(Base):
    """Notula rapat - ringkasan/keputusan dari draft s/d final. Satu baris
    per rapat (unique meeting_id), riwayat perubahan lihat MeetingNotulaRiwayat."""
    __tablename__ = "meeting_notula"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, unique=True)
    status = Column(Enum(StatusNotulaEnum), default=StatusNotulaEnum.kosong)
    ringkasan = Column(Text, default="[]")     # JSON list[str]
    keputusan = Column(Text, default="[]")     # JSON list[str] - legacy, tidak dipakai alur Buat Rapat baru
    pendahuluan = Column(Text, nullable=True)
    pertanyaan_jawaban = Column(Text, default="[]")   # JSON list[{"pertanyaan":..., "jawaban":...}]
    catatan_tambahan = Column(Text, nullable=True)
    sumber = Column(Enum(SumberNotulaEnum), nullable=True)
    versi = Column(Integer, default=1)
    difinalisasi_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    difinalisasi_pada = Column(DateTime, nullable=True)
    dibuat_pada = Column(DateTime, default=now_wib)
    diperbarui_pada = Column(DateTime, default=now_wib, onupdate=now_wib)

    meeting = relationship("Meeting")
    tindak_lanjut = relationship("MeetingTindakLanjut", back_populates="notula",
                                  cascade="all, delete-orphan")
    riwayat = relationship("MeetingNotulaRiwayat", back_populates="notula",
                            cascade="all, delete-orphan")


class MeetingNotulaRiwayat(Base):
    """Snapshot notula setiap kali difinalisasi atau dibuka kembali - dasar
    audit trail & pemulihan (§10, §12 rancangan)."""
    __tablename__ = "meeting_notula_riwayat"

    id = Column(Integer, primary_key=True, index=True)
    notula_id = Column(Integer, ForeignKey("meeting_notula.id"), nullable=False)
    versi = Column(Integer, nullable=False)
    snapshot = Column(Text, nullable=False)   # JSON: salinan penuh ringkasan/keputusan/tindak lanjut
    aksi = Column(Enum(AksiRiwayatNotulaEnum), nullable=False)
    alasan = Column(Text, nullable=True)      # wajib diisi untuk buka_kembali
    diubah_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    diubah_pada = Column(DateTime, default=now_wib)

    notula = relationship("MeetingNotula", back_populates="riwayat")


class MeetingTindakLanjut(Base):
    """Tindak lanjut rapat, direlasikan ke MeetingNotula (bukan langsung ke
    Meeting) - setara ActionItem lama tapi mengikuti siklus hidup notula baru."""
    __tablename__ = "meeting_tindak_lanjut"

    id = Column(Integer, primary_key=True, index=True)
    notula_id = Column(Integer, ForeignKey("meeting_notula.id"), nullable=False)
    deskripsi = Column(String(500))
    penanggung_jawab = Column(String(150), nullable=True)
    deadline = Column(String(20), nullable=True)
    status = Column(Enum(ActionStatusEnum), default=ActionStatusEnum.pending)

    notula = relationship("MeetingNotula", back_populates="tindak_lanjut")


class MeetingStatusLog(Base):
    """Audit trail setiap transisi lifecycle_status - ditulis oleh
    rapat_lifecycle.transisi(), tidak pernah ditulis langsung dari endpoint."""
    __tablename__ = "meeting_status_log"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    status_dari = Column(String(20), nullable=True)
    status_ke = Column(String(20), nullable=False)
    diubah_oleh = Column(Integer, ForeignKey("users.id"), nullable=True)
    diubah_pada = Column(DateTime, default=now_wib)
    catatan = Column(Text, nullable=True)

    meeting = relationship("Meeting")
