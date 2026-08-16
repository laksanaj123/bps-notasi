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
    jabatan: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    nama: str
    username: str
    email: Optional[str] = None
    password: str
    role: str = "pegawai"
    jabatan: Optional[str] = None


class UserAdminOut(BaseModel):
    id: int
    nama: str
    username: str
    email: Optional[str] = None
    role: str
    jabatan: Optional[str] = None
    is_active: bool
    must_reset_password: bool = False

    class Config:
        from_attributes = True


class UserDirectoryOut(BaseModel):
    """Directory ringan (bukan admin-only) untuk mengisi pilihan Pimpinan
    Rapat/Notulis/Peserta - lihat GET /api/users/directory."""
    id: int
    nama: str
    jabatan: Optional[str] = None
    role: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    nama: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    jabatan: Optional[str] = None
    is_active: Optional[bool] = None


# ---------- "Kelola Pengguna" gabungan (dulu Pegawai) - ringkasan seorang
# pengguna untuk pilihan Pimpinan Rapat/Notulis/Peserta & tampilan bersarang
# lain. Bentuk field TIDAK diubah (id/nama/jabatan) supaya kompatibel
# dengan frontend lama; sumber datanya kini tabel users, bukan pegawai. ----------
class PegawaiOut(BaseModel):
    id: int
    nama: str
    jabatan: Optional[str] = None

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


# ============================================================
# Alur rapat baru (lihat RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md).
# Terpisah dari schema Meeting* di atas - dipakai eksklusif oleh
# routers/rapat.py.
# ============================================================

# ---------- Rapat inti ----------
class RapatCreate(BaseModel):
    """Pembuatan rapat minimum: hanya judul & tanggal wajib."""
    judul_rapat: str
    tanggal: str
    unit_kerja: Optional[str] = None
    waktu_mulai: Optional[str] = None
    waktu_selesai: Optional[str] = None
    lokasi: Optional[str] = None
    jenis_media: Optional[str] = None
    pimpinan_id: Optional[int] = None
    agenda: Optional[str] = None
    catatan_notulis: Optional[str] = None   # "Keterangan"


class RapatUpdate(BaseModel):
    """Edit informasi rapat - semua field opsional, kirim yang ingin diubah saja."""
    judul_rapat: Optional[str] = None
    tanggal: Optional[str] = None
    unit_kerja: Optional[str] = None
    waktu_mulai: Optional[str] = None
    waktu_selesai: Optional[str] = None
    lokasi: Optional[str] = None
    jenis_media: Optional[str] = None
    pimpinan_id: Optional[int] = None
    notulis_id: Optional[int] = None
    agenda: Optional[str] = None
    catatan_notulis: Optional[str] = None


class AlasanRequest(BaseModel):
    """Payload untuk aksi yang mewajibkan alasan (batalkan, buka arsip)."""
    alasan: str


class RapatRingkasan(BaseModel):
    """Bagian dari RapatOut: hitungan agregat + status sub-entitas, dipakai
    untuk badge tab dan modal ringkasan pasca-rapat."""
    jumlah_peserta: int = 0
    jumlah_hadir: int = 0
    jumlah_dokumen: int = 0
    jumlah_rekaman: int = 0
    status_transkrip: Optional[str] = None
    status_notula: Optional[str] = None


class RapatOut(BaseModel):
    id: int
    judul_rapat: str
    tanggal: str
    unit_kerja: Optional[str] = None
    waktu_mulai: Optional[str] = None
    waktu_selesai: Optional[str] = None
    lokasi: Optional[str] = None
    jenis_media: Optional[str] = None
    agenda: Optional[str] = None
    catatan_notulis: Optional[str] = None
    pimpinan: Optional[PegawaiOut] = None
    notulis: Optional[PegawaiOut] = None
    lifecycle_status: str
    waktu_mulai_aktual: Optional[datetime] = None
    waktu_selesai_aktual: Optional[datetime] = None
    alasan_pembatalan: Optional[str] = None
    dibuat_pada: datetime
    ringkasan: RapatRingkasan = RapatRingkasan()

    class Config:
        from_attributes = True


class StatusLogOut(BaseModel):
    status_dari: Optional[str] = None
    status_ke: str
    diubah_oleh: Optional[str] = None   # nama pengguna, diisi manual saat serialisasi
    diubah_pada: datetime
    catatan: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Peserta & Kehadiran ----------
class KehadiranOut(BaseModel):
    status_kehadiran: str
    waktu_hadir: Optional[datetime] = None
    waktu_keluar: Optional[datetime] = None
    keterangan: Optional[str] = None
    dicatat_pada: Optional[datetime] = None
    diedit_pasca_rapat: bool = False

    class Config:
        from_attributes = True


class KehadiranUpdate(BaseModel):
    status_kehadiran: str
    waktu_hadir: Optional[datetime] = None
    waktu_keluar: Optional[datetime] = None
    keterangan: Optional[str] = None


class PesertaCreate(BaseModel):
    """Kirim user_id (pegawai internal) ATAU nama_manual (peserta eksternal)."""
    user_id: Optional[int] = None
    nama_manual: Optional[str] = None
    jabatan_manual: Optional[str] = None
    instansi_manual: Optional[str] = None
    peran: str = "peserta"


class PesertaUpdate(BaseModel):
    nama_manual: Optional[str] = None
    jabatan_manual: Optional[str] = None
    instansi_manual: Optional[str] = None
    peran: Optional[str] = None


class WalkinCreate(BaseModel):
    """Peserta yang hadir langsung tanpa terdaftar sebelumnya - membuat baris
    peserta (sumber=walk_in) & kehadiran (hadir) sekaligus."""
    nama_manual: str
    jabatan_manual: Optional[str] = None
    instansi_manual: Optional[str] = None
    waktu_hadir: Optional[datetime] = None
    keterangan: Optional[str] = None


class PesertaOut(BaseModel):
    id: int
    pegawai: Optional[PegawaiOut] = None   # nama field dipertahankan utk kompatibilitas frontend
    nama_manual: Optional[str] = None
    jabatan_manual: Optional[str] = None
    instansi_manual: Optional[str] = None
    peran: str
    sumber: str
    ditambahkan_pada: datetime
    kehadiran: Optional[KehadiranOut] = None

    class Config:
        from_attributes = True


# ---------- Dokumen ----------
class DokumenOut(BaseModel):
    id: int
    nama_file: str
    jenis: str
    url: str = ""
    mime_type: Optional[str] = None
    ukuran_bytes: Optional[int] = None
    versi: int = 1
    status: str
    diunggah_pasca_rapat: bool = False
    diunggah_pada: datetime

    class Config:
        from_attributes = True


# ---------- Rekaman ----------
class RekamanOut(BaseModel):
    id: int
    segmen_ke: int
    status: str
    durasi_detik: Optional[float] = None
    ukuran_bytes: Optional[int] = None
    url: str = ""
    pesan_error: Optional[str] = None
    mulai_pada: datetime
    selesai_pada: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Transkripsi ----------
class TranskripOut(BaseModel):
    id: int
    sumber: str
    status: str
    teks: Optional[str] = None
    bahasa: Optional[str] = None
    model_stt: Optional[str] = None
    pesan_error: Optional[str] = None
    mulai_pada: Optional[datetime] = None
    selesai_pada: Optional[datetime] = None

    class Config:
        from_attributes = True
        protected_namespaces = ()   # "model_stt" bukan field internal pydantic


class TranskripManualIn(BaseModel):
    teks: str


class TranskripUpdate(BaseModel):
    teks: str


# ---------- Notula & Tindak Lanjut ----------
class TindakLanjutIn(BaseModel):
    deskripsi: str = ""
    penanggung_jawab: Optional[str] = "Belum ditentukan"
    deadline: Optional[str] = "Belum ditentukan"
    status: Optional[str] = "Pending"


class TindakLanjutOut(BaseModel):
    id: int
    deskripsi: Optional[str] = None
    penanggung_jawab: Optional[str] = None
    deadline: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class PertanyaanJawabanIn(BaseModel):
    pertanyaan: str = ""
    jawaban: str = ""


class NotulaUpdate(BaseModel):
    """Autosave - kirim field yang berubah saja."""
    pendahuluan: Optional[str] = None
    ringkasan: Optional[List[str]] = None
    pertanyaan_jawaban: Optional[List[PertanyaanJawabanIn]] = None
    keputusan: Optional[List[str]] = None
    catatan_tambahan: Optional[str] = None


class NotulaOut(BaseModel):
    id: int
    status: str
    pendahuluan: Optional[str] = None
    ringkasan: List[str] = []
    pertanyaan_jawaban: List[PertanyaanJawabanIn] = []
    keputusan: List[str] = []
    catatan_tambahan: Optional[str] = None
    sumber: Optional[str] = None
    versi: int = 1
    difinalisasi_oleh: Optional[str] = None
    difinalisasi_pada: Optional[datetime] = None
    tindak_lanjut: List[TindakLanjutOut] = []

    class Config:
        from_attributes = True
