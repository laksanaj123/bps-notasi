# NOTASI — Notula Otomatis Berbasis Artificial Intelligence

Aplikasi web untuk BPS Kabupaten Sanggau: rekaman rapat diunggah/direkam →
diubah jadi teks (speech-to-text) → diringkas otomatis oleh AI (pembahasan,
keputusan, tindak lanjut) → disunting oleh notulis → diekspor ke Word/PDF
**mengikuti format resmi notula BPS Kabupaten Sanggau**, lengkap dengan
daftar peserta, tanda tangan Kepala BPS & Notulis, dan foto dokumentasi
kegiatan yang otomatis disisipkan ke dokumen.

Arsitektur client-server sederhana: frontend statis (HTML/Tailwind/vanilla
JS) memanggil REST API FastAPI, data disimpan di SQLite.

---

## Daftar Isi

1. [Struktur Proyek](#1-struktur-proyek)
2. [Dua Model Alur Rapat](#2-dua-model-alur-rapat)
3. [Instalasi & Menjalankan](#3-instalasi--menjalankan)
4. [Autentikasi & Peran Pengguna](#4-autentikasi--peran-pengguna)
5. [Provider AI: Demo / OpenAI / Lokal](#5-provider-ai-demo--openai--lokal)
6. [Alur Penggunaan](#6-alur-penggunaan)
7. [Ekspor Dokumen Word & PDF](#7-ekspor-dokumen-word--pdf)
8. [Referensi API](#8-referensi-api)
9. [Mempercepat Transkripsi](#9-mempercepat-transkripsi)
10. [Keterbatasan & Catatan Produksi](#10-keterbatasan--catatan-produksi)
11. [Troubleshooting](#11-troubleshooting)
12. [Kirim WhatsApp Otomatis](#12-kirim-whatsapp-otomatis)

---

## 1. Struktur Proyek

```
notasi-app/
├── backend/
│   ├── app/
│   │   ├── main.py                 <- app FastAPI, endpoint alur lama (/api/meetings), auth, users, dashboard
│   │   ├── models.py                <- seluruh tabel database (SQLAlchemy)
│   │   ├── schemas.py               <- validasi request/response (Pydantic)
│   │   ├── auth.py                  <- login, JWT, hashing password (bcrypt langsung), hak akses per-rapat
│   │   ├── config.py                 <- pengaturan aplikasi, dibaca dari .env
│   │   ├── database.py               <- engine SQLAlchemy & session
│   │   ├── rapat_lifecycle.py        <- state machine terpusat untuk siklus hidup Rapat (alur baru)
│   │   ├── routers/
│   │   │   └── rapat.py              <- seluruh endpoint alur baru (/api/rapat/*)
│   │   ├── data/pegawai_seed.py      <- data awal 29 pegawai BPS Kabupaten Sanggau (nama + jabatan)
│   │   ├── utils/
│   │   │   ├── indo_date.py          <- format tanggal/jam Bahasa Indonesia
│   │   │   ├── storage.py            <- simpan berkas unggahan dengan validasi ukuran
│   │   │   └── tz.py                 <- waktu WIB konsisten (now_wib())
│   │   └── services/
│   │       ├── transcription.py      <- speech-to-text (demo/openai/local + chunking paralel)
│   │       ├── summarizer.py         <- ringkasan AI (demo/openai/ollama)
│   │       ├── document_extract.py   <- ekstraksi teks dari materi rapat (PDF/DOCX/PPTX/TXT)
│   │       ├── docx_export.py        <- susun dokumen Word sesuai template resmi BPS Sanggau
│   │       └── pdf_export.py         <- konversi Word -> PDF via LibreOffice
│   ├── scripts/
│   │   └── migrate_pegawai_to_user.py  <- migrasi satu kali: tabel Pegawai lama -> User berrole pegawai
│   ├── requirements.txt              <- dependensi inti (cukup untuk mode demo/OpenAI)
│   ├── requirements-local-ai.txt     <- dependensi TAMBAHAN untuk mode STT lokal (faster-whisper)
│   └── .env.example
└── frontend/
    └── index.html                    <- seluruh antarmuka pengguna (SPA satu berkas)
```

## 2. Dua Model Alur Rapat

Codebase ini menjalankan **dua alur rapat berdampingan** di atas tabel
`meetings` yang sama, dibedakan oleh kolom `lifecycle_status`
(`NULL` = alur lama, terisi = alur baru). Ini bukan sisa kode mati — keduanya
aktif dan bisa dipakai dari UI yang sedang berjalan.

### Alur baru — **"Rapat"** (`/api/rapat/*`, `routers/rapat.py`)

Alur utama saat ini (ditandai badge **BARU** di sidebar). Merepresentasikan
siklus hidup rapat yang sesungguhnya — data boleh diisi bertahap, sebelum,
selama, atau sesudah rapat berlangsung. Rancangan lengkapnya ada di
`RANCANGAN_UX_ALUR_RAPAT_NOTASI_v1.md` (kepala dokumen itu masih berlabel
"draft rancangan", tapi seluruh state machine dan endpoint di dalamnya
**sudah diimplementasikan** — lihat `rapat_lifecycle.py`).

State machine (dijaga terpusat oleh `rapat_lifecycle.transisi()`, setiap
perpindahan tercatat di tabel `meeting_status_log`):

```
draft ──jadwalkan──> dijadwalkan ──┐
  │                                 │
  └──────────────mulai──────────────┴──> berlangsung ──akhiri──> selesai
                                                │                    │
                                           batalkan            mulai_transkripsi /
                                                │                mulai_notula
                                                v                    │
                                          dibatalkan                 v
                                                                diproses ──> review ──finalisasi──> diarsipkan
                                                                                ^                        │
                                                                                └─────buka_arsip──────────┘
```

Kapabilitas alur ini yang tidak ada di alur lama:
- Peserta punya kategori **diundang / tambahan / walk-in** dan **kehadiran**
  aktual terpisah (`meeting_peserta` + `meeting_kehadiran`).
- **Banyak segmen rekaman** per rapat, dengan mulai/pause/resume/selesai
  (`meeting_rekaman`) — mengakomodasi rapat yang rekamannya terputus/diulang.
- Dokumen berkategori (materi/undangan/dokumentasi/lainnya) dan bisa
  diunggah pasca-rapat (`meeting_dokumen`).
- Transkripsi bisa dari STT, tempel manual, atau ekstraksi dokumen
  (`meeting_transkrip`), dan boleh dimulai selagi rapat masih berlangsung.
- Notula (`meeting_notula`) punya status sendiri (`kosong → draft_ai/draft_manual
  → review → final`) dan riwayat setiap finalisasi/buka-kembali
  (`meeting_notula_riwayat`) — jadi rapat yang sudah diarsipkan tetap bisa
  dibuka kembali oleh admin/notulis untuk dikoreksi, dengan jejak audit.
- Hanya status **diarsipkan** yang read-only; status lain tetap bisa diedit
  bebas (peserta, dokumen, dst) — prinsip "jangan kunci data opsional".

### Alur lama — **"Buat Notula"** (`/api/meetings/*`, `main.py`)

Wizard linear: isi form lengkap sekali → unggah audio → proses AI →
`menunggu → diproses → selesai`/`gagal`. Masih aktif di menu **Arsip
Notula** dan **Buat Notula**, dan endpoint-nya tidak diubah oleh
penambahan alur baru. Peserta hanya kolom JSON tunggal (tanpa status
hadir), satu rekaman per rapat, tanpa kategori dokumen.

**Implikasi penting:** dashboard (`/api/dashboard/stats`) dan daftar
`/api/meetings` **hanya menghitung rapat dari alur lama**
(`lifecycle_status IS NULL`) — rapat dari alur baru punya daftar &
statistiknya sendiri di halaman **Rapat**. Keduanya belum digabung dalam
satu tampilan ringkasan.

### Halaman "Knowledge Base" — belum berfungsi

Menu **Knowledge Base** (badge **PRATINJAU**, admin-only) di sidebar masih
tampil, tapi router backend-nya (`routers/kb.py`, fitur RAG) sudah dihapus
saat pembersihan `2026-08-12` (lihat commit/backup
`backend/_backup_before_rag_removal_.../`). Halaman ini sekarang **tidak
memanggil endpoint apa pun** — murni shell UI yang belum dicabut. Jangan
andalkan menu ini sampai fiturnya dibangun ulang atau menunya dihapus.

## 3. Instalasi & Menjalankan

Dibutuhkan **Python 3.10+**.

```bash
cd notasi-app/backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Jalankan:

```bash
uvicorn app.main:app --reload --port 8000
```

Buka **http://localhost:8000** — frontend statis disajikan langsung oleh
FastAPI (`app.mount("/", StaticFiles(...))` di `main.py`). Login dengan
`admin` / `admin123` (bisa diubah lewat `DEFAULT_ADMIN_USERNAME` /
`DEFAULT_ADMIN_PASSWORD` di `.env`, hanya berlaku saat akun admin pertama
kali dibuat). Dokumentasi API interaktif: **http://localhost:8000/docs**.

Saat pertama kali start, sistem otomatis membuat akun admin default, lalu
mengisi **29 akun pegawai BPS Kabupaten Sanggau** (dari
`data/pegawai_seed.py`) ke tabel `users` berrole `pegawai` — langsung
tersedia sebagai pilihan Pimpinan Rapat, Notulis, dan Peserta pada form
(lihat §4 soal kredensial akun pegawai ini). Migrasi kolom database yang
kurang pada instalasi lama dijalankan otomatis (`_auto_migrate()` di
`main.py`) tanpa menghapus data.

## 4. Autentikasi & Peran Pengguna

- **Login**: JWT (`python-jose`), password di-hash dengan **bcrypt
  langsung** (bukan `passlib` — lihat §11 soal alasannya).
- **Dua role permanen**: `admin` dan `pegawai`. "Notulis" bukan role,
  melainkan **penugasan per-rapat**: siapa pun yang menjadi `notulis_id`
  sebuah rapat punya hak tulis penuh atas rapat itu (`assert_can_write_meeting()`
  di `auth.py`); admin selalu punya hak tulis di semua rapat.
- **Kelola Pengguna** (menu admin-only, `/api/users*`) sudah punya CRUD
  penuh lewat UI: tambah akun (`POST /api/auth/register`), ubah
  nama/email/jabatan/role/status aktif, dan hapus akun — dengan pengaman
  agar admin aktif terakhir tidak bisa dihapus/dinonaktifkan sendiri.
- Akun pegawai hasil seed awal dibuat dengan **password acak** dan
  `must_reset_password=True` — wajib ganti password saat login pertama.
  Untuk instalasi yang bermigrasi dari tabel `Pegawai` lama, gunakan
  `backend/scripts/migrate_pegawai_to_user.py` (menghasilkan laporan
  kredensial sementara — **jangan commit laporan ini ke git**, sudah
  di-`.gitignore`-kan sebagai `backend/migrasi_kredensial_*.txt`).

## 5. Provider AI: Demo / OpenAI / Lokal

STT (speech-to-text) dan LLM (peringkasan) dipilih **independen** lewat
`.env`, bisa dicampur bebas. Diubah juga bisa lewat UI: halaman
**Pengaturan** (admin-only, `PATCH /api/settings`) menerapkan override ke
proses berjalan tanpa restart server.

| Kebutuhan | `demo` | `openai` (berbayar) | Lokal/gratis |
|---|---|---|---|
| Speech-to-Text | data contoh | Whisper API (±US$0,006/menit) | **faster-whisper**, jalan di server sendiri |
| Peringkasan/LLM | data contoh | GPT API (`gpt-4o-mini` default) | **Ollama** + Llama 3 / Mistral |

Catatan: **Ollama tidak bisa transkripsi audio** — hanya model bahasa
(teks). Speech-to-text tetap perlu Whisper, hanya saja versi lokalnya
(`faster-whisper`) gratis dan tanpa API key.

### Mengaktifkan mode lokal (gratis)

**a. Speech-to-Text lokal:**
```bash
pip install -r requirements-local-ai.txt
```
```
STT_PROVIDER=local
WHISPER_LOCAL_MODEL=small    # default aplikasi; "medium" untuk akurasi lebih baik, "base"/"tiny" untuk uji cepat
WHISPER_LOCAL_DEVICE=cpu     # atau "cuda" jika ada GPU NVIDIA
```

**b. Peringkasan lokal (Ollama):**
1. Instal Ollama dari https://ollama.com
2. `ollama pull llama3` (atau `llama3.2:3b` untuk mesin lebih ringan)
3. Pastikan Ollama berjalan (`ollama serve`, biasanya otomatis sebagai service)
4. Di `.env`:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3
   ```

Jalankan ulang server setelah mengubah `.env`. Kombinasi paling praktis
untuk rapat panjang: `STT_PROVIDER=openai` (cepat & murah) +
`LLM_PROVIDER=ollama` (ringkasan tetap gratis & lokal) — lihat §9.

**Konsekuensi mode lokal:** kualitas bergantung pada model & perangkat.
`faster-whisper` model `small`/`medium` cukup akurat untuk Bahasa
Indonesia; Llama 3 8B via Ollama memadai untuk ringkasan tapi tidak
sekuat GPT-4 untuk rapat sangat kompleks. Server perlu RAM minimal ±8GB
untuk menjalankan keduanya dengan nyaman.

## 6. Alur Penggunaan

### 6.1 Alur Rapat (menu **Rapat**, direkomendasikan)

1. **+ Buat Rapat** — isi minimum Judul & Tanggal (field lain opsional,
   bisa dilengkapi kapan saja), simpan sebagai **Draft** atau
   **Dijadwalkan**.
2. Lengkapi peserta (undang dari direktori pegawai atau tambah manual),
   unggah dokumen pendukung, kapan pun sebelum/selama/sesudah rapat.
3. **Mulai Rapat** → status **Berlangsung**: catat kehadiran, tambah
   peserta walk-in, mulai/jeda/lanjut/hentikan rekaman (multi-segmen bila
   terputus).
4. **Akhiri Rapat** → **Selesai**. Bila ada rekaman, klik **Proses
   Transkripsi**; bila tidak, langsung pilih sumber notula (manual atau
   dari dokumen).
5. **Generate draft notula via LLM** (opsional, boleh dilewati untuk
   notula manual) → status **Review**: edit/koreksi ringkasan, keputusan,
   tanya-jawab, dan tindak lanjut.
6. **Finalisasi** → **Diarsipkan** (read-only). Perlu revisi setelah
   diarsipkan? **Buka Arsip** (admin/notulis, wajib isi alasan, tercatat
   di riwayat) mengembalikannya ke status Review.
7. **Export Word/PDF** tersedia di status apa pun setelah notula terisi.

### 6.2 Alur cepat lama (menu **Buat Notula** / **Arsip Notula**)

1. Isi Unit Kerja/Topik/Tanggal/Tempat/Waktu, pilih **Pimpinan Rapat** dan
   **Notulis** dari dropdown, centang **Peserta Rapat** yang hadir, isi
   agenda, unggah audio (dan materi rapat opsional) → **Proses dengan AI**.
2. Pemrosesan (STT → ringkasan) berjalan di **background thread**; bebas
   berpindah halaman, kemajuan dipantau lewat lingkaran progres 0–100%
   dan indikator mini di pojok kanan atas.
3. Tinjau & sunting hasil (klik teks ringkasan/keputusan langsung untuk
   edit, atau buka **Halaman Editor** bergaya dokumen penuh) → **Simpan**.
4. Unggah foto **Bukti Dokumentasi** bila ada — otomatis tersisip ke
   bagian "Dokumentasi Kegiatan" saat ekspor (2 foto per baris).
5. **Export Word/PDF**, **Cetak**, atau **Bagikan** (WhatsApp/Email/salin
   teks/Web Share API) dari Arsip.
6. **CRUD penuh** di Arsip: lihat pratinjau format resmi, edit metadata,
   proses ulang rapat gagal, hapus (beserta seluruh berkas terkait).

## 7. Ekspor Dokumen Word & PDF

Kedua alur (§2) memakai fungsi ekspor yang sama (`docx_export.py`), murni
`python-docx` tanpa dependensi tambahan. Struktur dokumen mengikuti
`template-notule-kegiatan.md`: kop surat BPS Kabupaten Sanggau berulang di
header tiap halaman, tabel info rapat (Unit Kerja/Tanggal/Topik/Tempat),
tabel peserta (Nama + Jabatan, 2 kolom berpasangan), paragraf Pendahuluan
tersusun otomatis dari tanggal/jam/pimpinan, bagian Pembahasan & Keputusan
Rapat, tabel Tindak Lanjut, blok tanda tangan **Mengetahui** (Kepala BPS —
dideteksi otomatis dari jabatan yang mengandung "Kepala BPS" di data
pegawai) & **Notulis**, ditutup lampiran foto Dokumentasi Kegiatan dan
transkripsi lengkap.

**Export PDF** mengonversi dokumen Word via **LibreOffice** (gratis,
lintas OS) sehingga hasil PDF identik dengan Word-nya — instal LibreOffice
di server bila tombol PDF menampilkan pesan error instalasi; export Word
tetap berfungsi tanpa LibreOffice.

Alamat/nama instansi di kop surat bisa disesuaikan lewat `NAMA_INSTANSI`
dan `ALAMAT_INSTANSI` di `.env` jika suatu saat dipakai satuan kerja lain.

## 8. Referensi API

Dokumentasi interaktif lengkap (semua parameter, skema request/response)
selalu tersedia di **`/docs`** saat server jalan. Ringkasan kelompok
endpoint:

| Area | Prefix | Contoh |
|---|---|---|
| Auth & sesi | `/api/auth` | `POST /login`, `GET /me`, `POST /register` (admin) |
| Pengguna | `/api/users` | `GET /`, `GET /directory`, `PATCH /{id}`, `DELETE /{id}` |
| Pengaturan AI | `/api/settings` | `GET`, `PATCH` (admin) |
| **Rapat (alur baru)** | `/api/rapat` | CRUD rapat, `/jadwalkan` `/mulai` `/akhiri` `/batalkan` `/buka-arsip`, `/peserta*`, `/dokumen*`, `/rekaman/*` (mulai/pause/resume/selesai), `/transkripsi/*`, `/notula/*` (generate/manual/edit/tindak-lanjut/finalisasi), `/riwayat-status`, `/export/docx`, `/export/pdf` |
| Rapat (alur lama) | `/api/meetings` | CRUD, `/process`, `/progress`, `/summary`, `/content`, `/bukti`, `/export/docx`, `/export/pdf` |
| Dashboard | `/api/dashboard` | `/stats` (hanya alur lama, lihat §2) |
| Konfigurasi publik | `/api/config` | info provider aktif, status LibreOffice, identitas instansi |

## 9. Mempercepat Transkripsi

**Di mana waktu sebenarnya habis?** Hampir seluruhnya di **transkripsi
(Whisper)**, bukan di peringkasan LLM.

### Sudah otomatis aktif

| Optimasi | Perkiraan dampak |
|---|---|
| Model default `small` (bukan `medium`) | ±3–5x lebih cepat |
| `beam_size=1` (greedy, bukan beam search 5) | ±2–3x lebih cepat |
| **VAD** — jeda/hening dibuang sebelum diproses | 30–60% lebih cepat pada rekaman rapat nyata |
| `cpu_threads` = semua inti CPU | 2–4x |
| **Batched inference** (faster-whisper ≥ 1.1) | 2–4x lebih cepat |
| `condition_on_previous_text=False` | Lebih cepat + mencegah loop halusinasi |
| **Pramuat model saat server start** | Rapat pertama tidak menunggu 1–3 menit |
| **Chunking paralel** untuk audio ≥ `WHISPER_CHUNK_THRESHOLD_MINUTES` (default 15 menit) | Mendekati Nx lebih cepat, N = `WHISPER_CHUNK_WORKERS` |

Setiap transkripsi mencetak kecepatan nyatanya di log server, mis.
`[NOTASI] Transkripsi: audio 180 dtk diproses dalam 42 dtk (4.3x realtime).`
— di atas 1x berarti lebih cepat daripada durasi audionya sendiri.

### Kalau masih kurang cepat, urutkan dari paling berdampak

1. **GPU NVIDIA** (10–30x): `WHISPER_LOCAL_DEVICE=cuda` (butuh CUDA + cuDNN).
2. **Turunkan model**: `WHISPER_LOCAL_MODEL=base` (atau `tiny` untuk uji coba).
3. **Naikkan `WHISPER_BATCH_SIZE`** (mis. 16) bila RAM mencukupi.
4. **Kualitas rekaman**: mikrofon dekat pembicara, mono, minim suara latar.
5. **LLM lebih ringan**: `ollama pull llama3.2:3b`, `OLLAMA_MODEL=llama3.2:3b`.

### Rapat berjam-jam

Dua jalan realistis untuk rekaman 2–3 jam:

**a. Whisper API OpenAI untuk STT saja** (`STT_PROVIDER=openai`,
`LLM_PROVIDER=ollama`) — ±Rp 6.000/jam audio, selesai dalam hitungan
menit; ringkasan tetap diproses lokal, hanya audio yang keluar server.

**b. Sepenuhnya lokal dengan chunking paralel** — audio di atas
`WHISPER_CHUNK_THRESHOLD_MINUTES` otomatis dipotong (via `ffmpeg`, tanpa
re-encode) menjadi bagian `WHISPER_CHUNK_MINUTES`, ditranskripsi paralel
di proses CPU terpisah. Butuh `ffmpeg` di PATH server
(`winget install Gyan.FFmpeg` / `apt install ffmpeg`); bila tidak ada,
otomatis kembali ke mode satu-proses tanpa membuat aplikasi gagal.
`WHISPER_CHUNK_WORKERS` sebaiknya = jumlah **core fisik** server (bukan
logical/hyperthread) — tiap worker memuat salinan model sendiri ke RAM.

## 10. Keterbatasan & Catatan Produksi

- **CORS** saat ini `allow_origins=["*"]` di `main.py` — batasi ke domain
  internal instansi sebelum dipakai produksi.
- **SECRET_KEY** di `.env` masih placeholder — wajib diganti nilai acak
  yang kuat sebelum deploy.
- **SQLite** cocok untuk skala kecil; migrasikan ke PostgreSQL
  (`DATABASE_URL`) untuk pemakaian banyak pengguna bersamaan.
- Folder `/media/bukti`, `/media/materi`, `/media/dokumen`, `/media/rekaman`
  disajikan **publik tanpa autentikasi** (agar `<img>`/unduhan langsung
  jalan di browser) — batasi akses jaringan di level firewall/VPN internal
  jika berkasnya sensitif.
- **Dashboard & statistik** hanya menghitung rapat dari alur lama (§2) —
  belum ada tampilan gabungan dengan alur Rapat baru.
- **Menu "Knowledge Base"** tampil di sidebar tapi tidak punya backend
  (§2) — jangan dipakai sampai dibangun ulang.
- `AUDIO_RETENTION_DAYS` (default 30 hari) dideklarasikan di `config.py`
  untuk penghapusan otomatis audio rapat yang sudah final/diarsipkan,
  tapi pastikan proses penjadwalannya (cron/scheduler) benar-benar
  berjalan di lingkungan produksi sebelum mengandalkannya.
- Backup berkala untuk `notasi.db`, folder `uploads/`, dan `exports/`.
- Jangan pernah commit `backend/.env`, `backend/notasi.db`, atau laporan
  kredensial hasil skrip migrasi (`backend/migrasi_kredensial_*.txt`) —
  semuanya sudah dikecualikan lewat `.gitignore`.

## 11. Troubleshooting

**Error bcrypt saat instalasi/login** (`module 'bcrypt' has no attribute
'__about__'`): sudah diperbaiki permanen — kode memakai `bcrypt` langsung
(bukan `passlib`), kompatibel dengan semua versi bcrypt 4.x/5.x.
`requirements.txt` menyematkan `bcrypt==4.0.1` yang terbukti stabil.

**`faster-whisper` "tidak ada"**: sengaja TIDAK ikut di `requirements.txt`
karena ukurannya besar dan hanya perlu untuk mode STT lokal. Instal
terpisah: `pip install -r requirements-local-ai.txt`.

**Export gagal dengan "no such column"**: terjadi bila `notasi.db`
berasal dari versi aplikasi lama. Server melakukan **migrasi otomatis**
saat dinyalakan (`_auto_migrate()` di `main.py`, menambah kolom yang
kurang tanpa menghapus data) — jalankan ulang server. Alternatif paling
bersih: hapus `notasi.db` (data lama hilang) lalu jalankan ulang.

**Export PDF error "LibreOffice tidak ditemukan"**: instal dari
https://www.libreoffice.org, jalankan ulang server. Di Windows, aplikasi
otomatis mencari di `C:\Program Files\LibreOffice`.

**Proses macet di status "Diproses" setelah server mati**: saat server
dinyalakan ulang, rapat (alur lama) yang tersangkut otomatis ditandai
"Gagal" dan bisa langsung diproses ulang dari Arsip.

**Ollama timeout ("Read timed out")**: model 8B di CPU bisa butuh lebih
dari 300 detik untuk transkrip panjang — naikkan `OLLAMA_TIMEOUT_SECONDS`,
atau pakai model lebih ringan (`ollama pull llama3.2:3b`).

**Output Ollama rusak/terpotong** (kata dobel, JSON tidak valid): gejala
umum dari offload otomatis ke GPU yang bermasalah di sebagian mesin.
`OLLAMA_NUM_GPU=0` (default) memaksa CPU-only sebagai setelan aman.

## 12. Kirim WhatsApp Otomatis

Undangan rapat & notula bisa dikirim ke WhatsApp pegawai lewat dua jalur,
tampil sebagai kartu "Kirim Undangan via WhatsApp" (tab Peserta) dan "Kirim
Notula via WhatsApp" (tab Notula) di halaman Detail Rapat:

- **Tautan `wa.me` manual** (`backend/app/services/whatsapp.py` tidak
  terlibat) — selalu aktif tanpa konfigurasi apa pun. Tiap peserta punya
  tombol yang membuka chat WhatsApp dengan pesan siap kirim; Anda tetap
  menekan tombol "Kirim" di WhatsApp sendiri (batasan `wa.me`: 1 penerima
  per tautan, tidak bisa dipicu otomatis oleh halaman web).
- **Kirim Otomatis** (server-side, **WhatsApp Cloud API resmi Meta** —
  bukan library tidak resmi seperti Baileys/whatsapp-web.js yang melanggar
  Ketentuan Layanan WhatsApp) — benar-benar terkirim tanpa klik manual sama
  sekali. Tombolnya baru muncul setelah kredensial diisi di `.env`.

### Blast undangan dari halaman "Rapat" (via whacenter — TIDAK RESMI)

Halaman sidebar **Rapat** (generator surat undangan) punya tombol **"Blast ke
WhatsApp"** yang mengirim *teks* undangan (tanpa lampiran) ke tiap penerima
ber-nomor lewat gateway pihak ketiga **whacenter** (`app.whacenter.com/api/send`
— HP yang sudah dipasangi bot). Ini **bukan jalur resmi Meta**, melanggar ToS
WhatsApp & berisiko nomor diblokir — **hanya untuk uji coba internal**. Aktifkan
dengan mengisi `WHACENTER_DEVICE_ID` di `.env` (Device ID perangkat yang sudah
scan QR di whacenter.my.id). Kosong → tombol menolak dengan pesan jelas, teks
tetap bisa disalin manual dari UI.

### Setup (gratis, ~10 menit)

Lihat komentar lengkap di `backend/.env.example` bagian "WHATSAPP CLOUD
API" — ringkasnya:

1. Buat App di [developers.facebook.com](https://developers.facebook.com)
   (use case "Other" → tipe "Business"), tambahkan produk **WhatsApp**.
2. Halaman **API Setup** app tsb memberi nomor uji coba gratis, Temporary
   Access Token, dan Phone Number ID → isi ke `WHATSAPP_ACCESS_TOKEN` /
   `WHATSAPP_PHONE_NUMBER_ID` di `.env`, lalu jalankan ulang server.
3. Tambahkan nomor penerima uji coba (maks 5, sebelum verifikasi bisnis)
   lewat "Manage phone number list" di halaman yang sama — nomor harus
   diverifikasi kode OTP dulu sebelum bisa dikirimi.
4. Buat 2 **message template** (WhatsApp Manager → Message Templates,
   kategori *Utility*) bernama persis `notasi_undangan` dan `notasi_notula`
   — isi body-nya ada di `.env.example` (variabel `{{1}}`, `{{2}}`, dst
   harus urut sama seperti di sana, karena kode mengirim parameter
   berurutan). Template biasanya disetujui dalam beberapa menit.

### Batasan platform (bukan bug aplikasi ini)

- WhatsApp **tidak mengizinkan teks bebas** ke nomor yang belum pernah
  membalas chat bisnis ini dalam 24 jam — karena itu kirim otomatis selalu
  lewat template yang sudah disetujui, bukan teks bebas.
- Mode belum-verifikasi-bisnis **hanya bisa kirim ke maks 5 nomor** yang
  didaftarkan manual sebagai penerima uji. Untuk mengirim ke nomor pegawai
  sungguhan secara bebas, akun WhatsApp Business perlu diverifikasi lewat
  Meta Business Manager (tetap gratis, tapi proses administratif terpisah
  di luar aplikasi ini).
- Nomor WhatsApp pegawai disimpan di `User.no_whatsapp` (diisi lewat form
  "Pengguna Baru" di halaman Kelola Pengguna). Kosong → dipakai nomor uji
  coba (`6285185461625`, ditandai "(nomor uji coba)" di UI) sebagai
  fallback, supaya fitur ini tetap bisa langsung dicoba tanpa mengisi
  nomor asli satu-satu dulu.
