"""
Speaker diarization opsional (pyannote.audio) - hanya dipakai alur "Rapat"
(routers/rapat.py) untuk memecah transkrip jadi per-pembicara.

Kalau paket 'pyannote.audio' belum terpasang, HUGGINGFACE_TOKEN kosong,
model gagal dimuat/diunduh, atau proses diarization itu sendiri gagal,
diarize_and_split() mengembalikan None (bukan raise) - transkripsi utama
tetap berjalan normal tanpa container per-speaker, sesuai desain "auto-disable"
aplikasi ini (lihat DIARIZATION_ENABLED di config.py).

Instalasi: pip install -r requirements-diarization.txt (lihat file itu untuk
cara mendapat HuggingFace token & menerima lisensi model).
"""
import time
from pathlib import Path

from ..config import settings

# Singleton lazy-load, sama pola seperti _get_local_model() di transcription.py.
_pipeline = None
_pipeline_unavailable = False


def _get_pipeline():
    global _pipeline, _pipeline_unavailable
    if _pipeline is not None:
        return _pipeline
    if _pipeline_unavailable:
        return None

    try:
        from pyannote.audio import Pipeline
    except ImportError:
        print("[NOTASI] Diarization dilewati: paket 'pyannote.audio' belum terpasang "
              "(pip install -r requirements-diarization.txt).")
        _pipeline_unavailable = True
        return None

    if not settings.HUGGINGFACE_TOKEN:
        print("[NOTASI] Diarization dilewati: HUGGINGFACE_TOKEN belum diisi di .env.")
        _pipeline_unavailable = True
        return None

    try:
        t0 = time.time()
        print(f"[NOTASI] Memuat model diarization '{settings.DIARIZATION_MODEL}'...")
        _pipeline = Pipeline.from_pretrained(
            settings.DIARIZATION_MODEL, use_auth_token=settings.HUGGINGFACE_TOKEN,
        )
        print(f"[NOTASI] Model diarization siap dalam {time.time() - t0:.1f} detik.")
        return _pipeline
    except Exception as e:
        print(f"[NOTASI] Diarization dilewati: gagal memuat model ({e}).")
        _pipeline_unavailable = True
        return None


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def diarize_and_split(audio_path: Path, whisper_segments: list[dict]) -> list[dict] | None:
    """Jalankan diarization pada `audio_path`, lalu kelompokkan
    `whisper_segments` ([{"start","end","text"}], dari transcribe_audio(...,
    return_segments=True)) per pembicara berdasarkan overlap waktu terbesar
    dengan speaker turn pyannote.

    Return list [{"speaker_label","urutan","teks"}] terurut dari pembicara
    paling banyak bicara (Pembicara 1 = paling banyak), atau None kalau
    diarization tidak bisa dijalankan atau cuma 1 suara terdeteksi (lihat
    modul docstring untuk kondisi fallback)."""
    if not settings.DIARIZATION_ENABLED or not whisper_segments:
        return None

    pipeline = _get_pipeline()
    if pipeline is None:
        return None

    try:
        t0 = time.time()
        diarization = pipeline(str(audio_path))
        print(f"[NOTASI] Diarization selesai dalam {time.time() - t0:.1f} detik.")
    except Exception as e:
        print(f"[NOTASI] Diarization dilewati: proses gagal ({e}).")
        return None

    turns = [(turn.start, turn.end, speaker) for turn, _, speaker in diarization.itertracks(yield_label=True)]
    if not turns:
        return None

    speaker_segments: dict[str, list[dict]] = {}
    speaker_duration: dict[str, float] = {}
    for seg in whisper_segments:
        best_speaker, best_overlap = None, 0.0
        for t_start, t_end, speaker in turns:
            ov = _overlap(seg["start"], seg["end"], t_start, t_end)
            if ov > best_overlap:
                best_overlap, best_speaker = ov, speaker
        if best_speaker is None:
            continue  # tidak ada overlap dengan speaker turn manapun (jeda/hening) - lewati
        speaker_segments.setdefault(best_speaker, []).append(seg)
        speaker_duration[best_speaker] = speaker_duration.get(best_speaker, 0.0) + (seg["end"] - seg["start"])

    if len(speaker_segments) < 2:
        return None  # cuma 1 suara terdeteksi - tidak perlu container terpisah

    ordered = sorted(speaker_segments.keys(), key=lambda s: speaker_duration.get(s, 0.0), reverse=True)
    result = []
    for idx, speaker in enumerate(ordered):
        segs = sorted(speaker_segments[speaker], key=lambda s: s["start"])
        teks = " ".join(s["text"] for s in segs).strip()
        result.append({"speaker_label": f"Pembicara {idx + 1}", "urutan": idx, "teks": teks})
    return result
