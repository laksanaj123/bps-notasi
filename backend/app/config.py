"""
Konfigurasi aplikasi NOTASI.
Semua nilai dapat diatur lewat file .env (lihat .env.example).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    # --- Umum ---
    APP_NAME: str = "NOTASI - Notula Otomatis Berbasis AI"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ganti-dengan-secret-key-acak-yang-panjang")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'notasi.db'}")

    # --- Penyimpanan berkas ---
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    BUKTI_DIR: Path = BASE_DIR / "uploads" / "bukti"
    MATERI_DIR: Path = BASE_DIR / "uploads" / "materi"
    EXPORT_DIR: Path = BASE_DIR / "exports"
    # Dipakai alur rapat baru (routers/rapat.py) - terpisah dari BUKTI_DIR/MATERI_DIR
    # lama supaya berkas kedua model data tidak tercampur.
    DOKUMEN_DIR: Path = BASE_DIR / "uploads" / "dokumen"
    REKAMAN_DIR: Path = BASE_DIR / "uploads" / "rekaman"
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "500"))
    MAX_IMAGE_MB: int = int(os.getenv("MAX_IMAGE_MB", "15"))
    MAX_MATERI_MB: int = int(os.getenv("MAX_MATERI_MB", "30"))
    # Batas panjang teks hasil ekstraksi per file materi, supaya tidak
    # membanjiri context window LLM lokal yang kecil.
    MAX_MATERI_CHARS: int = int(os.getenv("MAX_MATERI_CHARS", "20000"))

    # --- Retention audio: kandidat terbesar pemenuhan storage. File audio
    # rekaman (bukan transkrip/notula-nya) dihapus otomatis setelah N hari,
    # HANYA untuk rapat yang sudah final/diarsipkan (tidak pernah menghapus
    # audio rapat yang masih berjalan/direview). 0 = nonaktif. ---
    AUDIO_RETENTION_DAYS: int = int(os.getenv("AUDIO_RETENTION_DAYS", "30"))

    # =========================================================================
    # PROVIDER AI - dapat dipilih independen untuk Speech-to-Text (STT)
    # dan peringkasan (LLM), tanpa perlu mengubah kode.
    #
    #   STT_PROVIDER : "demo"  -> data contoh, tanpa biaya/API key (default)
    #                  "openai" -> OpenAI Whisper API (berbayar, perlu OPENAI_API_KEY)
    #                  "local"  -> faster-whisper, jalan di server sendiri, gratis
    #
    #   LLM_PROVIDER : "demo"   -> data contoh, tanpa biaya/API key (default)
    #                  "openai" -> OpenAI GPT (berbayar, perlu OPENAI_API_KEY)
    #                  "ollama" -> Ollama + Llama3/Mistral, jalan di server sendiri, gratis
    # =========================================================================
    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "demo").lower()
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "demo").lower()

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Whisper lokal (faster-whisper) - tanpa API key, jalan di CPU/GPU sendiri
    # -------- SETELAN KECEPATAN (lihat README bagian "Mempercepat Pemrosesan") --------
    # Ukuran model: tiny | base | small | medium | large-v3
    #   small  = pilihan seimbang untuk CPU (default). ~3-5x lebih cepat dari medium.
    #   base   = lebih cepat lagi, akurasi turun; cocok untuk audio jernih.
    #   medium = akurasi lebih baik, tapi berat di CPU.
    WHISPER_LOCAL_MODEL: str = os.getenv("WHISPER_LOCAL_MODEL", "small")
    WHISPER_LOCAL_DEVICE: str = os.getenv("WHISPER_LOCAL_DEVICE", "cpu")  # "cuda" bila ada GPU NVIDIA
    # int8 = tercepat di CPU; float16 = untuk GPU; kosongkan agar dipilih otomatis
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "")
    # beam_size=1 (greedy) ~2-3x lebih cepat dari default 5, akurasi turun tipis
    WHISPER_BEAM_SIZE: int = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
    # VAD memotong bagian hening/jeda rapat sebelum ditranskripsi.
    # Pada rekaman rapat nyata ini sering memangkas 30-60% durasi kerja.
    WHISPER_VAD: bool = os.getenv("WHISPER_VAD", "true").lower() in ("1", "true", "yes")
    # Jumlah thread CPU; 0 = pakai semua inti yang tersedia
    WHISPER_CPU_THREADS: int = int(os.getenv("WHISPER_CPU_THREADS", "0"))
    # Batched inference (faster-whisper >= 1.1): memproses beberapa potongan
    # audio sekaligus, bisa 2-4x lebih cepat. 0 = nonaktif.
    WHISPER_BATCH_SIZE: int = int(os.getenv("WHISPER_BATCH_SIZE", "8"))
    # Muat model ke memori saat server start, agar rapat pertama tidak
    # menunggu pemuatan model (yang bisa memakan 1-3 menit).
    WHISPER_PRELOAD: bool = os.getenv("WHISPER_PRELOAD", "true").lower() in ("1", "true", "yes")

    # -------- CHUNKING PARALEL (audio panjang) --------
    # Memotong audio panjang jadi beberapa bagian (via ffmpeg, tanpa re-encode)
    # lalu mentranskripsi tiap bagian di PROSES CPU terpisah sekaligus.
    # Butuh ffmpeg terpasang di server; jika tidak ada, otomatis kembali ke
    # mode biasa (satu proses, tanpa dipecah) tanpa membuat aplikasi gagal.
    WHISPER_CHUNK_ENABLED: bool = os.getenv("WHISPER_CHUNK_ENABLED", "true").lower() in ("1", "true", "yes")
    # Audio di bawah durasi ini (menit) diproses langsung tanpa dipecah -
    # untuk audio pendek, overhead pemotongan tidak sepadan.
    WHISPER_CHUNK_THRESHOLD_MINUTES: int = int(os.getenv("WHISPER_CHUNK_THRESHOLD_MINUTES", "15"))
    # Panjang tiap potongan audio, dalam menit.
    WHISPER_CHUNK_MINUTES: int = int(os.getenv("WHISPER_CHUNK_MINUTES", "10"))
    # Jumlah proses paralel. Cocokkan dengan jumlah CORE FISIK server (bukan
    # logical/hyperthread) - tiap proses memuat salinan model Whisper sendiri
    # ke RAM, jadi angka yang terlalu besar bisa membuat CPU/RAM rebutan
    # alih-alih lebih cepat. Default 2 aman untuk server kecil (2 core/8GB RAM).
    WHISPER_CHUNK_WORKERS: int = int(os.getenv("WHISPER_CHUNK_WORKERS", "2"))

    # Ollama - LLM lokal tanpa API key
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    # Model 8B di CPU lambat bisa melebihi 300 dtk untuk transkrip panjang;
    # naikkan bila sering gagal dengan pesan "Read timed out".
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
    # 0 = paksa CPU-only. Default aman: di beberapa mesin, offload sebagian
    # ke GPU (yang dipilih otomatis oleh Ollama) menghasilkan output rusak/
    # terpotong (kata dobel, JSON tidak valid) - gejala driver/GPU, bukan
    # masalah model. Naikkan (mis. 999 = semua layer ke GPU) hanya jika sudah
    # diuji dan hasilnya tetap benar di mesin Anda.
    OLLAMA_NUM_GPU: int = int(os.getenv("OLLAMA_NUM_GPU", "0"))

    @property
    def DEMO_MODE(self) -> bool:
        """True jika STT maupun LLM masih memakai data contoh (belum ada AI aktif)."""
        return self.STT_PROVIDER == "demo" and self.LLM_PROVIDER == "demo"

    # --- Default admin (dibuat otomatis saat pertama kali start) ---
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_ADMIN_NAME: str = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")

    # --- Identitas satuan kerja (dipakai di kop surat notulensi) ---
    UNIT_KERJA_DEFAULT: str = os.getenv("UNIT_KERJA_DEFAULT", "BPS Kabupaten Sanggau")
    NAMA_INSTANSI: str = os.getenv("NAMA_INSTANSI", "BADAN PUSAT STATISTIK KABUPATEN SANGGAU")
    ALAMAT_INSTANSI: str = os.getenv(
        "ALAMAT_INSTANSI",
        "Jalan Sutan Syahrir Nomor 52 A, Sanggau 78512 ; Telepon : (+62-564) 21844 ; "
        "Laman https://sanggaukab.bps.go.id/ ; Post-el bps6105@bps.go.id",
    )

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.BUKTI_DIR.mkdir(parents=True, exist_ok=True)
settings.MATERI_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
settings.DOKUMEN_DIR.mkdir(parents=True, exist_ok=True)
settings.REKAMAN_DIR.mkdir(parents=True, exist_ok=True)
