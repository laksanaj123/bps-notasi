"""
Layanan peringkasan rapat dengan 3 provider yang dapat dipilih lewat .env
(LLM_PROVIDER=demo|openai|ollama), tanpa perlu mengubah kode apa pun:

  demo    -> hasil contoh, tanpa biaya, tanpa API key (default)
  openai  -> OpenAI GPT (mis. gpt-4o-mini), berbayar, perlu OPENAI_API_KEY
  ollama  -> Ollama + Llama3/Mistral, berjalan di server sendiri, GRATIS,
             tanpa API key (butuh aplikasi Ollama terpasang & `ollama pull llama3`)

Mengubah transkrip mentah menjadi struktur:
  - ringkasan: list[str]
  - keputusan: list[str]
  - tindak_lanjut: list[dict]  ({deskripsi, penanggung_jawab, deadline})
"""
import json
import re
from ..config import settings

SYSTEM_PROMPT = """Anda adalah asisten AI yang bertugas membuat notulensi rapat instansi pemerintah.
Baca transkrip rapat berikut, lalu hasilkan output HANYA dalam format JSON valid
(tanpa teks tambahan, tanpa markdown code fence) dengan struktur persis seperti ini:

{
  "ringkasan": ["poin ringkasan 1", "poin ringkasan 2", ...],
  "keputusan": ["keputusan 1", "keputusan 2", ...],
  "tindak_lanjut": [
    {"deskripsi": "...", "penanggung_jawab": "...", "deadline": "YYYY-MM-DD atau teks singkat"}
  ]
}

Gunakan Bahasa Indonesia formal. Jika informasi penanggung jawab atau deadline tidak
disebutkan eksplisit dalam transkrip, isi dengan "Belum ditentukan".

Jika ada "Catatan kasar notulis" dan/atau "Materi rapat" pada input, perlakukan
keduanya sebagai sumber tambahan yang setara pentingnya dengan transkrip: gabungkan
poin-poinnya ke ringkasan/keputusan/tindak lanjut yang relevan, dan pakai untuk
melengkapi hal yang terlewat atau kurang jelas terdengar di transkrip (mis. nama
penanggung jawab, deadline, angka/target dari dokumen pendukung, atau keputusan
yang disebut notulis tapi tidak terucap jelas di rekaman).

Jika ada "Konteks dari dokumen referensi/pedoman", itu BUKAN bagian dari rapat -
transkrip tetap satu-satunya sumber tentang apa yang benar-benar dibahas/diputuskan.
Pakai konteks itu HANYA untuk membantu Anda memahami istilah, singkatan, aturan, atau
angka yang disebut sekilas di transkrip; jangan menambahkan poin ringkasan/keputusan
yang isinya berasal dari dokumen referensi tapi tidak disinggung di transkrip."""

SYSTEM_PROMPT_RINGKAS = """Anda adalah asisten AI yang bertugas membuat notulensi rapat instansi pemerintah.
Baca transkrip rapat berikut, lalu hasilkan output HANYA dalam format JSON valid
(tanpa teks tambahan, tanpa markdown code fence) dengan struktur persis seperti ini:

{
  "ringkasan": ["poin pembahasan 1", "poin pembahasan 2", ...],
  "pertanyaan_jawaban": [
    {"pertanyaan": "...", "jawaban": "..."}
  ]
}

Gunakan Bahasa Indonesia formal. "ringkasan" berisi poin-poin pembahasan rapat.
"pertanyaan_jawaban" berisi sesi tanya-jawab yang terjadi dalam rapat (jika ada) -
kosongkan array-nya bila tidak ada sesi tanya jawab yang tercatat di transkrip.

Jika ada "Catatan kasar notulis" dan/atau "Materi rapat" pada input, perlakukan
keduanya sebagai sumber tambahan yang setara pentingnya dengan transkrip: gabungkan
poin-poinnya ke pembahasan yang relevan, dan pakai untuk melengkapi hal yang
terlewat atau kurang jelas terdengar di transkrip.

Jika ada "Konteks dari dokumen referensi/pedoman", itu BUKAN bagian dari rapat -
transkrip tetap satu-satunya sumber tentang apa yang benar-benar dibahas. Pakai
konteks itu HANYA untuk membantu Anda memahami istilah/aturan/angka yang disebut
sekilas di transkrip; jangan menambahkan poin pembahasan yang isinya berasal dari
dokumen referensi tapi tidak disinggung di transkrip."""


def _demo_result() -> dict:
    return {
        "ringkasan": [
            "Progres digitalisasi mencapai 72% dari target tahunan",
            "Penyerapan anggaran sebesar 58%, masih sesuai rencana semester",
            "Modul NOTASI diusulkan untuk mulai digunakan bulan depan",
        ],
        "keputusan": [
            "Modul NOTASI disepakati mulai digunakan bulan depan",
            "Tim diminta menyiapkan rencana tindak lanjut implementasi",
        ],
        "tindak_lanjut": [
            {"deskripsi": "Menyiapkan rencana tindak lanjut implementasi NOTASI",
             "penanggung_jawab": "Belum ditentukan", "deadline": "Belum ditentukan"},
            {"deskripsi": "Melaporkan realisasi anggaran semester berjalan",
             "penanggung_jawab": "Belum ditentukan", "deadline": "Belum ditentukan"},
        ],
    }


def _demo_result_ringkas() -> dict:
    return {
        "ringkasan": [
            "Progres digitalisasi mencapai 72% dari target tahunan",
            "Penyerapan anggaran sebesar 58%, masih sesuai rencana semester",
            "Modul NOTASI diusulkan untuk mulai digunakan bulan depan",
        ],
        "pertanyaan_jawaban": [
            {"pertanyaan": "Kapan modul NOTASI mulai digunakan?",
             "jawaban": "Diusulkan mulai digunakan bulan depan setelah persiapan selesai."},
        ],
    }


def _build_user_prompt(transcript_text: str, meeting_context: dict) -> str:
    prompt = (
        f"Judul rapat: {meeting_context.get('judul_rapat')}\n"
        f"Tanggal: {meeting_context.get('tanggal')}\n"
        f"Pimpinan rapat: {meeting_context.get('pimpinan')}\n"
        f"Peserta: {meeting_context.get('peserta')}\n"
        f"Agenda: {meeting_context.get('agenda')}\n"
    )
    materi_rapat = (meeting_context.get("materi_rapat") or "").strip()
    if materi_rapat:
        prompt += f"\nMateri rapat (dokumen pendukung):\n{materi_rapat}\n"
    catatan_notulis = (meeting_context.get("catatan_notulis") or "").strip()
    if catatan_notulis:
        prompt += f"\nCatatan kasar notulis:\n{catatan_notulis}\n"
    prompt += f"\nTranskrip rapat:\n{transcript_text}"
    return prompt


def _extract_json(text: str) -> dict:
    """Mengambil objek JSON pertama dari teks, untuk berjaga-jaga jika model
    lokal (Ollama) menambahkan kalimat pembuka/penutup di luar JSON.

    Melempar RuntimeError bila gagal - SENGAJA tidak diam-diam jatuh ke data
    demo, karena itu akan membuat kegagalan AI sungguhan (mis. model rusak/
    menghasilkan output kosong) tampak seperti berhasil dengan isi generik
    yang menyesatkan pengguna."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    cuplikan = (text or "(kosong)")[:200]
    raise RuntimeError(f"Respons model AI bukan JSON valid, tidak bisa diproses. Cuplikan: {cuplikan!r}")


def _summarize_openai(transcript_text: str, meeting_context: dict, system_prompt: str = SYSTEM_PROMPT) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(transcript_text, meeting_context)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return _extract_json(response.choices[0].message.content)


def _summarize_ollama(transcript_text: str, meeting_context: dict, system_prompt: str = SYSTEM_PROMPT) -> dict:
    import requests
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(transcript_text, meeting_context)},
        ],
        "format": "json",   # Ollama >= 0.1.29 mendukung mode output JSON
        "stream": False,
        "options": {"temperature": 0.2, "num_gpu": settings.OLLAMA_NUM_GPU},
    }
    # Model lokal yang lebih kecil kadang menghasilkan JSON terpotong/rusak
    # (bervariasi antar percobaan walau prompt sama) - coba beberapa kali
    # sebelum benar-benar menyerah, daripada langsung menandai rapat gagal
    # karena satu percobaan yang sial.
    percobaan_terakhir = None
    for percobaan in range(3):
        resp = requests.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload,
                              timeout=settings.OLLAMA_TIMEOUT_SECONDS)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        try:
            return _extract_json(content)
        except RuntimeError as e:
            percobaan_terakhir = e
    raise percobaan_terakhir


def _normalize_list(value) -> list:
    """Model (terutama LLM lokal yang lebih kecil) kadang membalas field yang
    seharusnya array sebagai satu string panjang, bukan list. Normalisasi ini
    mencegah error validasi/500 saat hasil ditampilkan (lihat MeetingDetailOut)."""
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        return [line.strip("-*• ").strip() for line in value.splitlines() if line.strip()]
    if value:
        return [str(value)]
    return []


def _normalize_tindak_lanjut(value) -> list:
    if not isinstance(value, list):
        value = [value] if value else []
    hasil = []
    for item in value:
        if not isinstance(item, dict):
            continue
        hasil.append({
            "deskripsi": str(item.get("deskripsi", "")),
            "penanggung_jawab": str(item.get("penanggung_jawab") or "Belum ditentukan"),
            "deadline": str(item.get("deadline") or "Belum ditentukan"),
        })
    return hasil


def _normalize_qa(value) -> list:
    if not isinstance(value, list):
        value = [value] if value else []
    hasil = []
    for item in value:
        if not isinstance(item, dict):
            continue
        pertanyaan = str(item.get("pertanyaan", "")).strip()
        jawaban = str(item.get("jawaban", "")).strip()
        if not pertanyaan and not jawaban:
            continue
        hasil.append({"pertanyaan": pertanyaan, "jawaban": jawaban})
    return hasil


def summarize_transcript(transcript_text: str, meeting_context: dict, struktur: str = "lengkap") -> dict:
    """struktur="lengkap" (default, dipakai alur Buat Notula lama): ringkasan +
    keputusan + tindak_lanjut. struktur="ringkas" (alur Buat Rapat baru):
    ringkasan + pertanyaan_jawaban saja."""
    system_prompt = SYSTEM_PROMPT if struktur == "lengkap" else SYSTEM_PROMPT_RINGKAS

    if settings.LLM_PROVIDER == "openai":
        data = _summarize_openai(transcript_text, meeting_context, system_prompt)
    elif settings.LLM_PROVIDER == "ollama":
        data = _summarize_ollama(transcript_text, meeting_context, system_prompt)
    else:
        data = _demo_result() if struktur == "lengkap" else _demo_result_ringkas()

    data["ringkasan"] = _normalize_list(data.get("ringkasan"))
    if struktur == "lengkap":
        data["keputusan"] = _normalize_list(data.get("keputusan"))
        data["tindak_lanjut"] = _normalize_tindak_lanjut(data.get("tindak_lanjut"))
    else:
        data["pertanyaan_jawaban"] = _normalize_qa(data.get("pertanyaan_jawaban"))
    return data
