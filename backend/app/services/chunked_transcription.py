"""
Transkripsi paralel untuk audio panjang (misal rapat 4-5 jam).

Pendekatan: audio dipotong dengan ffmpeg memakai stream-copy (`-c copy`,
tanpa re-encode sehingga pemotongan sangat cepat), lalu tiap potongan
ditranskripsi di PROSES CPU terpisah sekaligus lewat ProcessPoolExecutor.
Tiap proses worker memuat salinan model Whisper-nya sendiri (memakai
singleton lazy-load yang sama seperti mode biasa, lihat transcription.py),
jadi jumlah worker sebaiknya mengikuti jumlah core FISIK server, bukan
jumlah logical/hyperthread - lihat WHISPER_CHUNK_WORKERS di config.py.

Jika ffmpeg tidak tersedia di server, otomatis kembali ke transkripsi
satu-proses biasa tanpa membuat aplikasi gagal.
"""
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ..config import settings

# Kandidat lokasi ffmpeg/ffprobe di berbagai OS, mengikuti pola find_soffice()
# di pdf_export.py.
_FFMPEG_CANDIDATES = [
    "ffmpeg",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
]
_FFPROBE_CANDIDATES = [
    "ffprobe",
    r"C:\ffmpeg\bin\ffprobe.exe",
    r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
]


def _find_exe(candidates: list[str]) -> str | None:
    for cand in candidates:
        found = shutil.which(cand)
        if found:
            return found
        if Path(cand).exists():
            return cand
    return None


def _ffmpeg_available() -> tuple[str, str] | None:
    ffmpeg = _find_exe(_FFMPEG_CANDIDATES)
    ffprobe = _find_exe(_FFPROBE_CANDIDATES)
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    return None


def _get_duration_seconds(ffprobe: str, file_path: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _split_audio(ffmpeg: str, file_path: Path, chunk_seconds: int, out_dir: Path,
                  duration: float) -> list[Path]:
    ext = file_path.suffix or ".wav"
    chunk_paths = []
    start = 0.0
    idx = 0
    while start < duration:
        out_path = out_dir / f"chunk_{idx:03d}{ext}"
        subprocess.run(
            [ffmpeg, "-y", "-ss", str(start), "-i", str(file_path),
             "-t", str(chunk_seconds), "-c", "copy", str(out_path)],
            capture_output=True, check=True,
        )
        chunk_paths.append(out_path)
        start += chunk_seconds
        idx += 1
    return chunk_paths


def _transcribe_chunk_worker(chunk_path_str: str, return_segments: bool = False):
    """Dijalankan di proses worker terpisah. Import di dalam fungsi supaya
    tiap proses hanya memuat apa yang dibutuhkannya (dan model Whisper-nya
    sendiri, lazy, lewat singleton milik proses tsb - lihat transcription.py)."""
    from .transcription import _transcribe_local_raw
    return _transcribe_local_raw(Path(chunk_path_str), return_segments=return_segments)


def transcribe_local_chunked(file_path: Path, progress_cb=None, return_segments: bool = False):
    """Mentranskripsi `file_path` memakai chunking paralel bila memenuhi
    syarat (ffmpeg tersedia & audio cukup panjang), jika tidak otomatis
    kembali ke transkripsi satu-proses biasa.

    progress_cb(fraction: float, stage: str) dipanggil dengan fraction 0..1
    tiap kali satu potongan selesai, jika diberikan.

    return_segments=True mengembalikan tuple (teks, segments) - timestamp
    tiap segmen diberi offset sesuai posisi potongannya supaya tetap relatif
    ke keseluruhan berkas audio, bukan ke awal potongan masing-masing.
    """
    from .transcription import _transcribe_local_raw

    if not settings.WHISPER_CHUNK_ENABLED:
        return _transcribe_local_raw(file_path, return_segments=return_segments, progress_cb=progress_cb)

    exes = _ffmpeg_available()
    if not exes:
        return _transcribe_local_raw(file_path, return_segments=return_segments, progress_cb=progress_cb)
    ffmpeg, ffprobe = exes

    try:
        duration = _get_duration_seconds(ffprobe, file_path)
    except Exception:
        return _transcribe_local_raw(file_path, return_segments=return_segments, progress_cb=progress_cb)

    threshold_seconds = settings.WHISPER_CHUNK_THRESHOLD_MINUTES * 60
    if duration <= threshold_seconds:
        return _transcribe_local_raw(file_path, return_segments=return_segments, progress_cb=progress_cb)

    chunk_seconds = max(60, settings.WHISPER_CHUNK_MINUTES * 60)
    workers = max(1, settings.WHISPER_CHUNK_WORKERS)

    with tempfile.TemporaryDirectory(prefix="notasi_chunks_") as tmp:
        tmp_dir = Path(tmp)
        chunk_paths = _split_audio(ffmpeg, file_path, chunk_seconds, tmp_dir, duration)
        n = len(chunk_paths)
        if n <= 1:
            return _transcribe_local_raw(file_path, return_segments=return_segments, progress_cb=progress_cb)

        results: list = [None] * n
        completed = 0

        with ProcessPoolExecutor(max_workers=min(workers, n)) as executor:
            future_to_idx = {
                executor.submit(_transcribe_chunk_worker, str(p), return_segments): i
                for i, p in enumerate(chunk_paths)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
                completed += 1
                if progress_cb:
                    progress_cb(completed / n, f"Transkripsi potongan {completed}/{n} audio")

        if not return_segments:
            return " ".join(r.strip() for r in results if r)

        texts = []
        all_segments = []
        for idx, r in enumerate(results):
            if not r:
                continue
            text, segs = r
            texts.append(text.strip())
            offset = idx * chunk_seconds
            for s in segs:
                all_segments.append({"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"]})
        return " ".join(texts), all_segments
