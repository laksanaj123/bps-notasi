"""
Layanan Speech-to-Text dengan 3 provider yang dapat dipilih lewat .env
(STT_PROVIDER=demo|openai|local), tanpa perlu mengubah kode apa pun:

  demo    -> transkrip contoh, tanpa biaya, tanpa API key (default)
  openai  -> OpenAI Whisper API, berbayar (~$0.006/menit audio), perlu OPENAI_API_KEY
  local   -> faster-whisper, berjalan di server sendiri, GRATIS, tanpa API key
             (butuh `pip install faster-whisper` dan CPU/GPU yang memadai)
"""
import os
import time
from pathlib import Path
from ..config import settings

DEMO_TRANSCRIPT = """Pimpinan: Selamat pagi, terima kasih sudah hadir dalam rapat hari ini.
Ahmad Fauzi: Terima kasih, Pak. Untuk progres digitalisasi, saat ini sudah mencapai 72% dari target.
Siti Rahmawati: Dari sisi anggaran, penyerapan kita sudah 58%, masih on track untuk semester ini.
Budi Santoso: Untuk timeline berikutnya, kami mengusulkan agar modul NOTASI bisa mulai digunakan bulan depan.
Pimpinan: Baik, kita sepakati itu sebagai keputusan rapat. Mohon disiapkan rencana tindak lanjutnya.
"""

# Model faster-whisper dimuat sekali saja (lazy singleton) supaya tidak
# di-load ulang setiap kali ada permintaan transkripsi.
_local_model = None
_batched_pipeline = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "Paket 'faster-whisper' belum terpasang (paket ini sengaja dipisah "
                "karena berukuran besar). Jalankan: pip install -r requirements-local-ai.txt "
                "lalu jalankan ulang server."
            ) from e

        device = settings.WHISPER_LOCAL_DEVICE
        compute_type = settings.WHISPER_COMPUTE_TYPE or ("int8" if device == "cpu" else "float16")
        cpu_threads = settings.WHISPER_CPU_THREADS or (os.cpu_count() or 4)

        t0 = time.time()
        print(f"[NOTASI] Memuat model Whisper '{settings.WHISPER_LOCAL_MODEL}' "
              f"({device}/{compute_type}, {cpu_threads} thread CPU)...")
        _local_model = WhisperModel(
            settings.WHISPER_LOCAL_MODEL,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,   # penting: tanpa ini hanya sebagian inti CPU dipakai
        )
        print(f"[NOTASI] Model Whisper siap dalam {time.time() - t0:.1f} detik.")
    return _local_model


def _get_transcriber():
    """Memakai BatchedInferencePipeline bila tersedia (faster-whisper >= 1.1):
    beberapa potongan audio diproses sekaligus sehingga jauh lebih cepat.
    Bila versi faster-whisper lebih lama, otomatis kembali ke mode biasa."""
    global _batched_pipeline
    model = _get_local_model()
    if settings.WHISPER_BATCH_SIZE <= 0:
        return model, False
    if _batched_pipeline is None:
        try:
            from faster_whisper import BatchedInferencePipeline
            _batched_pipeline = BatchedInferencePipeline(model=model)
            print("[NOTASI] Batched inference aktif (pemrosesan lebih cepat).")
        except Exception:
            _batched_pipeline = False   # tidak tersedia; jangan dicoba lagi
    if _batched_pipeline:
        return _batched_pipeline, True
    return model, False


def reset_local_model():
    """Dipanggil saat setelan Whisper lokal diubah lewat halaman Pengaturan,
    supaya model lama tidak terus dipakai - model baru dimuat lazy pada
    transkripsi berikutnya sesuai settings.WHISPER_LOCAL_MODEL saat itu."""
    global _local_model, _batched_pipeline
    _local_model = None
    _batched_pipeline = None


def preload_stt_model():
    """Dipanggil saat server start (thread terpisah) agar rapat pertama tidak
    ikut menanggung waktu pemuatan model, yang bisa memakan 1-3 menit."""
    if settings.STT_PROVIDER == "local" and settings.WHISPER_PRELOAD:
        try:
            _get_transcriber()
        except Exception as e:
            print(f"[NOTASI] Pramuat model Whisper gagal: {e}")


def _transcribe_openai(file_path: Path) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=settings.WHISPER_MODEL,
            file=audio_file,
            language="id",
        )
    return transcript.text


def _transcribe_local_raw(file_path: Path) -> str:
    """Transkripsi satu berkas audio, satu proses, tanpa chunking.
    Dipanggil langsung untuk audio pendek, dan dipanggil oleh tiap proses
    worker saat chunking paralel aktif (lihat chunked_transcription.py)."""
    transcriber, is_batched = _get_transcriber()

    kwargs = dict(
        language="id",
        beam_size=settings.WHISPER_BEAM_SIZE,       # 1 = greedy, 2-3x lebih cepat
        vad_filter=settings.WHISPER_VAD,            # buang jeda/hening sebelum diproses
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,           # cegah loop halusinasi & lebih cepat
    )
    if is_batched:
        kwargs["batch_size"] = settings.WHISPER_BATCH_SIZE

    t0 = time.time()
    segments, info = transcriber.transcribe(str(file_path), **kwargs)
    teks = " ".join(seg.text.strip() for seg in segments)  # generator: kerja nyata terjadi di sini
    elapsed = time.time() - t0
    durasi_audio = getattr(info, "duration", 0) or 0
    if durasi_audio:
        print(f"[NOTASI] Transkripsi: audio {durasi_audio:.0f} dtk diproses dalam "
              f"{elapsed:.0f} dtk ({durasi_audio / max(elapsed, 0.1):.1f}x realtime).")
    return teks


def _transcribe_local(file_path: Path, progress_cb=None) -> str:
    """Untuk audio panjang, delegasikan ke chunking paralel (lihat
    chunked_transcription.py); modul itu sendiri yang memutuskan apakah
    syarat chunking terpenuhi (ffmpeg tersedia, audio cukup panjang), dan
    kembali ke jalur biasa di bawah ini bila tidak."""
    from .chunked_transcription import transcribe_local_chunked
    return transcribe_local_chunked(file_path, progress_cb=progress_cb)


def transcribe_audio(file_path: Path, progress_cb=None) -> str:
    """Mengubah berkas audio menjadi teks, sesuai STT_PROVIDER yang aktif.

    progress_cb(fraction: float, stage: str), bila diberikan, dipanggil
    dengan fraction 0..1 selama transkripsi berlangsung (hanya didukung
    untuk mode "local" dengan chunking; provider lain mengabaikannya)."""
    if settings.STT_PROVIDER == "openai":
        return _transcribe_openai(file_path)
    if settings.STT_PROVIDER == "local":
        return _transcribe_local(file_path, progress_cb=progress_cb)
    return DEMO_TRANSCRIPT
