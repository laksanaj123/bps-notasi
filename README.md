# NOTASI — Notula Otomatis Berbasis Artificial Intelligence

Sistem lengkap: unggah rekaman rapat → diubah jadi teks (speech-to-text) →
diringkas otomatis oleh AI (pembahasan, keputusan, tindak lanjut) → bisa
disunting → diekspor ke Word **mengikuti format resmi notula BPS Kabupaten
Sanggau** (`template-notule-kegiatan.md`), lengkap dengan daftar peserta dari
`Daftar_Pegawai.md` dan foto bukti dokumentasi kegiatan yang otomatis
disisipkan ke dokumen.

## Struktur Proyek

```
notasi-app/
├── backend/
│   ├── app/
│   │   ├── main.py                    <- seluruh endpoint API
│   │   ├── models.py                  <- struktur tabel database
│   │   ├── schemas.py                 <- validasi request/response
│   │   ├── auth.py                    <- login & JWT
│   │   ├── config.py                  <- pengaturan (.env)
│   │   ├── data/pegawai_seed.py       <- data pegawai (dari Daftar_Pegawai.md)
│   │   ├── utils/indo_date.py         <- format tanggal/jam Bahasa Indonesia
│   │   └── services/
│   │       ├── transcription.py       <- speech-to-text (demo/openai/local)
│   │       ├── summarizer.py          <- ringkasan AI (demo/openai/ollama)
│   │       └── docx_export.py         <- export Word sesuai template BPS Sanggau
│   ├── requirements.txt               <- dependensi inti (cukup untuk mode demo/OpenAI)
│   ├── requirements-local-ai.txt      <- dependensi TAMBAHAN untuk mode lokal
│   └── .env.example
└── frontend/
    └── index.html                     <- antarmuka pengguna
```

## 1. Instalasi

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

Buka **http://localhost:8000**, login dengan `admin` / `admin123`.
Dokumentasi API: **http://localhost:8000/docs**.

Saat pertama kali start, sistem otomatis mengisi **29 data pegawai BPS
Kabupaten Sanggau** (dari `Daftar_Pegawai.md` yang Anda kirim) ke database —
langsung muncul sebagai pilihan Pimpinan Rapat, Notulis, dan Peserta Rapat
pada form, tidak perlu diketik manual lagi.

## 2. Soal API Key: Berbayar atau Gratis?

**OpenAI (Whisper + GPT) → berbayar per pemakaian.** Tidak ada API key gratis
dari OpenAI. Kira-kira US$0,006/menit audio untuk Whisper, plus biaya token
untuk ringkasan (murah jika pakai `gpt-4o-mini`, tapi tetap berbayar).

**Alternatif 100% gratis, tanpa API key sama sekali** — jalan sepenuhnya di
komputer/server Anda sendiri:

| Kebutuhan | Provider berbayar (OpenAI) | Provider lokal (gratis) |
|---|---|---|
| Speech-to-Text | Whisper API | **faster-whisper** (model Whisper yang sama, jalan lokal) |
| Peringkasan/LLM | GPT API | **Ollama** + Llama 3 / Mistral |

Catatan: **Ollama tidak bisa transkripsi audio** — Ollama hanya untuk model
bahasa (teks). Untuk audio-ke-teks tetap perlu Whisper, hanya saja versi
lokalnya (`faster-whisper`) yang gratis dan tidak butuh API key.

### Cara mengaktifkan mode lokal (gratis)

**a. Speech-to-Text lokal (faster-whisper):**
```bash
pip install -r requirements-local-ai.txt
```
Di `.env`:
```
STT_PROVIDER=local
WHISPER_LOCAL_MODEL=medium   # pakai "small" jika perangkat terbatas
WHISPER_LOCAL_DEVICE=cpu     # atau "cuda" jika ada GPU NVIDIA
```

**b. Peringkasan lokal (Ollama + Llama 3):**
1. Instal Ollama dari https://ollama.com
2. Unduh model: `ollama pull llama3` (atau `ollama pull mistral`)
3. Pastikan Ollama berjalan (`ollama serve`, biasanya otomatis jalan sebagai service)
4. Di `.env`:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3
   ```

Jalankan ulang server setelah mengubah `.env`. Bisa dicampur bebas — misalnya
STT pakai OpenAI (karena hasilnya lebih akurat) tapi ringkasan pakai Ollama
(karena gratis), atau sepenuhnya lokal, atau sepenuhnya OpenAI. Halaman
**Pengaturan** di aplikasi menampilkan provider mana yang sedang aktif.

**Konsekuensi mode lokal:** kualitas transkripsi/ringkasan bergantung pada
kekuatan model & perangkat. `faster-whisper` model "medium" cukup akurat
untuk Bahasa Indonesia; Llama 3 8B via Ollama cukup baik untuk ringkasan
tapi tidak sekuat GPT-4 untuk kasus rapat yang sangat kompleks. Server perlu
RAM minimal ±8GB untuk menjalankan keduanya dengan nyaman.

## 3. Template Dokumen Word

Ekspor `.docx` mengikuti struktur `template-notule-kegiatan.md` yang Anda
kirim: kop surat BPS Kabupaten Sanggau berulang di header setiap halaman,
tabel info rapat (Unit Kerja/Tanggal/Topik/Tempat), tabel peserta (Nama +
Jabatan, 2 kolom berpasangan seperti aslinya), paragraf Pendahuluan yang
disusun otomatis dari tanggal/jam/pimpinan rapat, bagian Pembahasan &
Keputusan Rapat, tabel Tindak Lanjut, blok tanda tangan Mengetahui (Kepala
BPS — dideteksi otomatis dari jabatan "Kepala BPS" di data pegawai) &
Notulis, ditutup dengan lampiran foto Dokumentasi Kegiatan dan transkripsi
lengkap.

Alamat/nama instansi di kop surat bisa disesuaikan lewat `NAMA_INSTANSI` dan
`ALAMAT_INSTANSI` di `.env` jika suatu saat dipakai satuan kerja lain.

## 4. Fitur Upload Bukti Dokumentasi

Setelah AI selesai memproses (atau saat membuka arsip rapat yang sudah
selesai), muncul kartu **"Bukti Dokumentasi Kegiatan"** — unggah beberapa
foto sekaligus (drag multiple file), langsung tampil sebagai thumbnail, dan
**otomatis tersisip ke bagian "Dokumentasi Kegiatan"** saat dokumen Word
diekspor (2 foto per baris, sesuai gaya template asli). Foto bisa dihapus
kembali dengan tombol × yang muncul saat hover.

## 5. Alur Penggunaan

1. **Buat Notula** → isi Unit Kerja/Topik/Tanggal/Tempat/Waktu, pilih
   **Pimpinan Rapat** dan **Notulis** dari dropdown, centang **Peserta Rapat**
   yang hadir (semua dari daftar pegawai, tidak perlu ketik manual), isi
   agenda, unggah audio → **Proses dengan AI**.
2. Tinjau & sunting hasil (klik teks ringkasan/keputusan langsung untuk edit) → **Simpan**.
3. Unggah foto **Bukti Dokumentasi** jika ada.
4. **Export Word** → dokumen `.docx` lengkap sesuai format resmi langsung terunduh.
5. Semua rapat tersimpan di **Arsip Notula**; rekap tampil di **Dashboard**/**Statistik**.

## 6. Catatan Sebelum Dipakai Produksi

- **CORS** saat ini `allow_origins=["*"]` — batasi ke domain internal instansi.
- **SECRET_KEY** wajib diganti dengan nilai acak yang kuat.
- **SQLite** cocok untuk skala kecil; migrasikan ke PostgreSQL (`DATABASE_URL`) untuk pemakaian banyak pengguna bersamaan.
- **Proses AI berjalan sinkron** — untuk rekaman sangat panjang (>1 jam), sebaiknya dipindah ke background task/queue agar tidak timeout.
- Folder `/media/bukti` disajikan **publik tanpa autentikasi** (agar `<img>` di browser bisa menampilkannya langsung) — batasi akses jaringan di level firewall/VPN internal bila foto rapat bersifat sensitif.
- **Export PDF** dan **manajemen pengguna via UI** belum diimplementasikan — beri tahu jika ingin ditambahkan.
- Backup berkala untuk `notasi.db`, folder `uploads/`, dan `exports/`.

## 7. Pemetaan ke Rancangan Aktualisasi

Kode ini mengimplementasikan tahapan "Pengembangan Aplikasi" hingga
"Pengujian Aplikasi": arsitektur client-server (HTML/Tailwind/JS ↔ FastAPI),
Whisper (API atau lokal) untuk speech-to-text, LLM (GPT atau Ollama) untuk
ringkasan/keputusan/tindak lanjut, SQLite sebagai basis data, python-docx
untuk ekspor dokumen sesuai template resmi satuan kerja — sesuai spesifikasi
teknis pada BAB I gagasan aktualisasi, dengan opsi tambahan agar tidak
bergantung pada layanan berbayar pihak ketiga.

## 8. Yang Baru pada Versi Ini

- **Export Word & PDF keduanya berfungsi.** Export Word murni python-docx (tanpa
  dependensi tambahan). Export PDF mengonversi dokumen Word via **LibreOffice**
  (gratis) sehingga hasil PDF identik dengan Word-nya — instal LibreOffice di
  server bila tombol PDF menampilkan pesan error instalasi.
- **Pemrosesan AI berjalan di background.** Setelah menekan "Proses dengan AI",
  Anda bebas berpindah halaman; kemajuan dipantau lewat **lingkaran progres
  0–100%** dengan kata-kata status yang bergilir, plus **indikator mini di pojok
  kanan atas** yang bisa diklik untuk kembali ke tampilan proses (berubah hijau
  "Selesai ✓" bila proses tuntas saat Anda berada di halaman lain).
- **CRUD penuh di Arsip Notula:** Lihat (pratinjau berformat template resmi
  lengkap dengan kop, tabel peserta, dan tanda tangan), Edit (metadata rapat),
  Hapus (beserta seluruh berkas), Proses Ulang untuk rapat yang gagal, tombol
  **Cetak** (print-ready, hanya dokumen yang tercetak), dan **Bagikan**
  (WhatsApp, Email, salin teks, atau bagikan berkas Word langsung dari peramban
  yang mendukung Web Share API).

## 9. Troubleshooting

**Error bcrypt saat instalasi/login** (`module 'bcrypt' has no attribute
'__about__'`): sudah diperbaiki permanen — kode tidak lagi memakai passlib,
melainkan bcrypt langsung, sehingga kompatibel dengan semua versi bcrypt.
requirements.txt juga sudah menyematkan `bcrypt==4.0.1` yang terbukti stabil.

**faster-whisper "tidak ada"**: paket ini memang sengaja TIDAK ikut di
requirements.txt karena ukurannya besar dan hanya perlu bila memakai mode STT
lokal. Instal terpisah: `pip install -r requirements-local-ai.txt`. Jika lupa,
aplikasi kini menampilkan pesan error yang menjelaskan perintah instalasinya.

**Export gagal dengan "no such column"**: terjadi bila `notasi.db` berasal dari
versi aplikasi lama. Versi ini melakukan **migrasi otomatis** saat server
dinyalakan (menambah kolom yang kurang tanpa menghapus data) — cukup jalankan
ulang server. Alternatif paling bersih: hapus `notasi.db` (data lama hilang)
lalu jalankan ulang.

**Export PDF error "LibreOffice tidak ditemukan"**: instal LibreOffice dari
https://www.libreoffice.org, lalu jalankan ulang server. Di Windows, aplikasi
otomatis mencari di `C:\Program Files\LibreOffice`. Export Word tetap berfungsi
tanpa LibreOffice.

**Proses macet di status "Diproses" setelah server mati**: saat server
dinyalakan ulang, rapat tersebut otomatis ditandai "Gagal" dan bisa langsung
di-"Proses Ulang" dari halaman Arsip.

## 10. Mempercepat Pemrosesan

**Di mana waktu sebenarnya habis?** Hampir seluruhnya di **transkripsi
(Whisper)**, bukan di peringkasan LLM. Konfigurasi awal aplikasi ini kebetulan
memilih setelan paling lambat yang mungkin (model `medium`, beam search 5,
tanpa VAD, thread CPU tidak diatur). Versi ini memperbaikinya.

### Yang sudah otomatis aktif sekarang

| Optimasi | Perkiraan dampak |
|---|---|
| Model default `small` (bukan `medium`) | ±3–5x lebih cepat |
| `beam_size=1` (greedy, bukan beam search 5) | ±2–3x lebih cepat |
| **VAD** — jeda/hening dibuang sebelum diproses | 30–60% lebih cepat pada rekaman rapat nyata |
| `cpu_threads` = semua inti CPU | 2–4x (default lama hanya memakai sebagian inti) |
| **Batched inference** (faster-whisper ≥ 1.1) | 2–4x lebih cepat |
| `condition_on_previous_text=False` | Lebih cepat + mencegah loop halusinasi |
| **Pramuat model saat server start** | Rapat pertama tidak menunggu 1–3 menit |
| **Chunking paralel** untuk audio panjang (≥ 15 menit, lihat §10 "Rapat berjam-jam") | Mendekati Nx lebih cepat, N = `WHISPER_CHUNK_WORKERS` |

Efeknya berlipat. Audio 3 menit yang tadinya belasan menit umumnya turun ke
kisaran **kurang dari satu menit** di CPU biasa. Setiap transkripsi kini juga
mencetak kecepatan nyatanya di log server, misalnya:
`[NOTASI] Transkripsi: audio 180 dtk diproses dalam 42 dtk (4.3x realtime).`
Angka **"x realtime"** inilah tolok ukur Anda — di atas 1x berarti lebih cepat
daripada durasi audionya sendiri.

### Kalau masih kurang cepat

Urutkan dari yang paling berdampak:

1. **Pakai GPU NVIDIA** (paling besar dampaknya, 10–30x):
   `WHISPER_LOCAL_DEVICE=cuda` di `.env` (butuh CUDA + cuDNN terpasang).
2. **Turunkan model** ke `base` (atau bahkan `tiny` untuk uji coba):
   `WHISPER_LOCAL_MODEL=base`. Untuk audio rapat yang jernih, `base` sering
   masih memadai, dan hasil AI tetap bisa disunting manual sebelum diekspor.
3. **Naikkan `WHISPER_BATCH_SIZE`** (mis. 16) bila RAM mencukupi.
4. **Kualitas rekaman** sangat berpengaruh: mikrofon dekat pembicara,
   satu berkas mono, hindari suara latar. Rekaman yang jernih mempercepat
   sekaligus memperbaiki akurasi.
5. **LLM lebih ringan**: `ollama pull llama3.2:3b`, lalu `OLLAMA_MODEL=llama3.2:3b`.
   Model 3B jauh lebih ringan daripada Llama 3 8B di CPU.

### Rapat berjam-jam — pertimbangkan ini

Untuk rekaman 2–3 jam, transkripsi lokal di CPU tetap akan makan waktu lama
(bahkan pada setelan tercepat, hitungannya masih puluhan menit). Ada dua jalan
realistis:

**a. Whisper API OpenAI — cepat dan sebenarnya sangat murah.**
Tarifnya ±US$0,006 per menit audio, jadi rapat **1 jam ≈ Rp 6.000**, dan
prosesnya biasanya selesai dalam hitungan menit, bukan puluhan menit. Untuk
volume rapat kantor pada umumnya, biaya sebulan kemungkinan besar masih di
bawah Rp 100.000. Kombinasi paling praktis:

```
STT_PROVIDER=openai     # transkripsi cepat & akurat, biaya kecil
LLM_PROVIDER=ollama     # peringkasan tetap gratis & lokal
```

Ini juga menjaga data ringkasan tetap diolah di server sendiri, sementara yang
dikirim keluar hanya berkas audio untuk ditranskripsi.

**b. Tetap sepenuhnya lokal, dengan chunking paralel.** Audio di atas
`WHISPER_CHUNK_THRESHOLD_MINUTES` (default 15 menit) otomatis dipotong
(via `ffmpeg`, tanpa re-encode) menjadi beberapa bagian `WHISPER_CHUNK_MINUTES`
(default 10 menit), lalu tiap bagian ditranskripsi di **proses CPU terpisah
sekaligus** — bukan berurutan. Butuh `ffmpeg` terpasang di PATH server
(`winget install Gyan.FFmpeg` di Windows, atau `apt install ffmpeg` di
Linux); bila tidak ada, otomatis kembali ke mode satu-proses biasa tanpa
membuat aplikasi gagal.

Setel `WHISPER_CHUNK_WORKERS` sesuai jumlah **core FISIK** server (bukan
logical/hyperthread) — tiap proses worker memuat salinan model Whisper-nya
sendiri ke RAM, jadi angka yang kebesaran justru membuat CPU/RAM rebutan.
Untuk server kecil (2 core/8GB RAM), nilai 2 sudah wajar; jangan naikkan
tanpa memastikan RAM mencukupi (model `small` ±0,5–1GB per proses).

Karena pemrosesan sudah berjalan di latar belakang, server bisa ditinggal dan
statusnya tetap terpantau di halaman Arsip — chunking paralel membuat
"semalam" itu jadi jauh lebih pendek.

Bila kebijakan instansi melarang audio keluar dari lingkungan internal,
opsi (b) plus GPU (atau server dengan lebih banyak core fisik) adalah
kombinasi yang paling masuk akal.

## 11. Halaman Editor Notula (baru)

Tombol **Edit** pada Arsip (dan tombol "Editor Lengkap" pada halaman hasil AI)
membuka **halaman editor bergaya dokumen** — tampilannya menyerupai lembar
notula jadi, tetapi seluruh bagiannya dapat langsung disunting:

- **Metadata**: unit kerja, topik, tanggal, tempat, waktu, pimpinan, notulis, agenda
- **Peserta**: klik "Ubah daftar peserta" untuk mencentang pegawai yang hadir;
  tabel peserta langsung menyesuaikan
- **Pembahasan & Keputusan**: klik poin untuk mengetik; tombol "+ Tambah poin"
  untuk menambah, tanda × untuk menghapus
- **Tindak Lanjut**: tabel dengan baris yang bisa ditambah/dihapus (uraian, PIC,
  deadline, status)
- **Transkripsi lengkap**: dapat dikoreksi manual bila ada kesalahan hasil AI
- **Bukti Dokumentasi Kegiatan**: unggah foto (drag & drop atau klik), langsung
  tergabung ke bagian "Dokumentasi Kegiatan" pada dokumen Word/PDF hasil ekspor

Tekan **Simpan Perubahan**, atau **Simpan & Pratinjau** untuk langsung melihat
hasil akhirnya dalam format notula resmi (yang dari sana bisa dicetak, dibagikan,
atau diekspor).

Catatan: menyunting rapat yang berstatus "Gagal" lalu menyimpannya akan mengubah
statusnya menjadi "Selesai", sehingga notula tetap bisa diekspor meski proses AI
sempat bermasalah — isinya cukup diketik/dikoreksi manual.
