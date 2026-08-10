from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    nama: str
    username: str
    role: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    nama: str
    username: str
    email: Optional[str] = None
    password: str
    role: str = "pegawai"


# ---------- Pegawai (direktori pegawai, untuk pilihan pimpinan/notulis/peserta) ----------
class PegawaiOut(BaseModel):
    id: int
    nama: str
    jabatan: str

    class Config:
        from_attributes = True


# ---------- Action Items ----------
class ActionItemOut(BaseModel):
    id: int
    deskripsi: str
    penanggung_jawab: Optional[str] = None
    deadline: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ActionItemUpdate(BaseModel):
    deskripsi: Optional[str] = None
    penanggung_jawab: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


# ---------- Dokumentasi / Bukti ----------
class DocumentationOut(BaseModel):
    id: int
    file_path: str
    keterangan: Optional[str] = ""
    url: str = ""   # diisi manual saat serialisasi (lihat main.py)

    class Config:
        from_attributes = True


# ---------- Materi Rapat ----------
class MaterialOut(BaseModel):
    id: int
    nama_asli: str
    url: str = ""   # diisi manual saat serialisasi (lihat main.py)

    class Config:
        from_attributes = True


# ---------- Meeting ----------
class MeetingOut(BaseModel):
    id: int
    unit_kerja: Optional[str] = None
    judul_rapat: str
    tanggal: str
    waktu_mulai: Optional[str] = None
    waktu_selesai: Optional[str] = None
    lokasi: Optional[str] = None
    agenda: Optional[str] = None
    catatan_notulis: Optional[str] = None
    status: str
    progress: int = 0
    progress_stage: Optional[str] = ""
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingUpdate(BaseModel):
    """Payload penyuntingan metadata rapat (Update pada CRUD arsip)."""
    unit_kerja: Optional[str] = None
    judul_rapat: Optional[str] = None
    tanggal: Optional[str] = None
    waktu_mulai: Optional[str] = None
    waktu_selesai: Optional[str] = None
    lokasi: Optional[str] = None
    agenda: Optional[str] = None
    catatan_notulis: Optional[str] = None
    pimpinan_id: Optional[int] = None
    notulis_id: Optional[int] = None
    peserta_ids: Optional[List[int]] = None


class ProgressOut(BaseModel):
    id: int
    status: str
    progress: int
    progress_stage: Optional[str] = ""


class MeetingDetailOut(MeetingOut):
    pimpinan: Optional[PegawaiOut] = None
    notulis: Optional[PegawaiOut] = None
    peserta: List[PegawaiOut] = []
    transkripsi: Optional[str] = None
    ringkasan: List[str] = []
    keputusan: List[str] = []
    tindak_lanjut: List[ActionItemOut] = []
    dokumentasi: List[DocumentationOut] = []
    materi: List[MaterialOut] = []


class SummaryUpdate(BaseModel):
    ringkasan: Optional[List[str]] = None
    keputusan: Optional[List[str]] = None


class ActionItemIn(BaseModel):
    """Satu baris tindak lanjut yang dikirim dari halaman editor."""
    deskripsi: str = ""
    penanggung_jawab: Optional[str] = "Belum ditentukan"
    deadline: Optional[str] = "Belum ditentukan"
    status: Optional[str] = "Pending"


class MeetingContentUpdate(BaseModel):
    """Simpan-semua dari halaman Editor: isi rapat disunting sekaligus.
    Field yang tidak dikirim tidak diubah."""
    transkripsi: Optional[str] = None
    ringkasan: Optional[List[str]] = None
    keputusan: Optional[List[str]] = None
    tindak_lanjut: Optional[List[ActionItemIn]] = None


# ---------- Pengaturan mode AI ----------
class AppSettingsOut(BaseModel):
    stt_provider: str
    llm_provider: str
    ollama_model: str
    whisper_local_model: str
    openai_api_key_set: bool
    openai_api_key_masked: Optional[str] = None


class AppSettingsUpdate(BaseModel):
    stt_provider: Optional[str] = None
    llm_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_model: Optional[str] = None
    whisper_local_model: Optional[str] = None


class DashboardStats(BaseModel):
    total_rapat: int
    notulensi_bulan_ini: int
    total_arsip: int
    grafik_per_bulan: dict
