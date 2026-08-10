import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float
)
from sqlalchemy.orm import relationship
from .database import Base


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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(150), nullable=False)
    username = Column(String(80), unique=True, index=True, nullable=False)
    email = Column(String(150), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.pegawai)
    created_at = Column(DateTime, default=datetime.utcnow)

    meetings = relationship("Meeting", back_populates="pembuat")


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
    """Direktori pegawai (di-seed dari Daftar_Pegawai.md). Dipakai untuk mengisi
    pilihan Pimpinan Rapat, Notulis, dan Peserta Rapat pada form notulensi."""
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

    # --- Pihak-pihak terkait (referensi ke tabel pegawai) ---
    pimpinan_id = Column(Integer, ForeignKey("pegawai.id"), nullable=True)
    notulis_id = Column(Integer, ForeignKey("pegawai.id"), nullable=True)
    peserta_ids = Column(Text, default="[]")   # JSON list[int] id pegawai peserta

    # --- Berkas & status pemrosesan AI ---
    file_audio = Column(String(500))
    durasi_detik = Column(Float, default=0)
    status = Column(Enum(StatusEnum), default=StatusEnum.menunggu)
    progress = Column(Integer, default=0)            # 0-100, diperbarui background worker
    progress_stage = Column(String(255), default="")  # keterangan tahap yang sedang berjalan
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    pembuat = relationship("User", back_populates="meetings")
    pimpinan = relationship("Pegawai", foreign_keys=[pimpinan_id])
    notulis = relationship("Pegawai", foreign_keys=[notulis_id])
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
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcript")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True)
    ringkasan = Column(Text)          # JSON string (list[str])
    keputusan = Column(Text)          # JSON string (list[str])
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    tanggal_export = Column(DateTime, default=datetime.utcnow)

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
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="materi")


class Documentation(Base):
    """Bukti/dokumentasi kegiatan (foto) yang diunggah pengguna, akan disisipkan
    ke bagian 'Dokumentasi Kegiatan Rapat' pada dokumen notulensi hasil ekspor."""
    __tablename__ = "documentation"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    file_path = Column(String(500))     # path relatif terhadap BUKTI_DIR
    keterangan = Column(String(255), default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="dokumentasi")
