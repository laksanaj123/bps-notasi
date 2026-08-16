# Deploy NOTASI ke VPS

Panduan ini men-deploy backend FastAPI + frontend statis + Ollama (LLM lokal)
+ faster-whisper (STT lokal) dalam 3 container Docker di belakang reverse
proxy Caddy (HTTPS otomatis). Cocok untuk mode AI lokal (`STT_PROVIDER=local`,
`LLM_PROVIDER=ollama`) yang butuh proses jalan terus-menerus dengan RAM/CPU
memadai — bukan untuk PaaS gratis/ephemeral.

## 1. Sizing VPS

- **Minimum**: 4 vCPU / 8 GB RAM, disk 40+ GB SSD, Ubuntu 22.04/24.04.
  (Whisper `small` ~1-2GB RAM + Ollama `llama3.2:3b` ~3-4GB RAM, keduanya
  jalan bersamaan saat proses rapat.)
- Kalau anggaran terbatas dan volume rapat rendah, bisa coba 2 vCPU/4GB RAM
  dengan `WHISPER_LOCAL_MODEL=base` dan `WHISPER_CHUNK_WORKERS=1`, tapi
  proses akan jauh lebih lambat dan berisiko OOM saat rapat panjang.
- Provider: DigitalOcean, Hetzner, Contabo, dsb — pilih salah satu, panduan
  ini generik untuk Ubuntu + Docker.

## 2. Siapkan DNS

Arahkan A record domain/subdomain (mis. `notasi.instansi.go.id`) ke IP
publik VPS. Caddy butuh ini untuk menerbitkan sertifikat TLS otomatis
(Let's Encrypt) — pastikan port 80 & 443 terbuka di firewall VPS sebelum
lanjut.

## 3. Install Docker di VPS

```bash
ssh root@IP_VPS
curl -fsSL https://get.docker.com | sh
```

(Perintah resmi Docker; sudah termasuk Compose plugin `docker compose`.)

## 4. Clone repo & konfigurasi

```bash
git clone <url-repo-anda> notasi-app
cd notasi-app/notasi-app   # sesuaikan jika struktur folder repo Anda beda

cp .env.production.example .env
nano .env
```

Isi minimal yang WAJIB diubah di `.env`:
- `DOMAIN` — domain yang sudah di-set DNS-nya di langkah 2.
- `SECRET_KEY` — generate dengan `openssl rand -hex 32`.
- `DEFAULT_ADMIN_PASSWORD` — jangan pakai default.
- `CORS_ORIGINS` — samakan dengan `https://DOMAIN`.
- `NAMA_INSTANSI` / `ALAMAT_INSTANSI` / `UNIT_KERJA_DEFAULT` — sesuaikan.

## 5. Jalankan

```bash
docker compose up -d --build
docker compose ps
```

Tunggu sampai image FastAPI selesai build (LibreOffice + faster-whisper
lumayan berat, bisa 5-10 menit di build pertama).

Pull model Ollama (one-time, ukuran beberapa GB):

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

Ganti `llama3.2:3b` kalau `OLLAMA_MODEL` di `.env` Anda ubah ke model lain.

## 6. Verifikasi

- `docker compose logs -f app` — pastikan tidak ada error saat startup
  (auto-migrate SQLite, load model Whisper karena `WHISPER_PRELOAD=true`).
- Buka `https://DOMAIN` di browser — harus muncul halaman login NOTASI
  dengan sertifikat TLS valid (Caddy otomatis).
- Login pakai `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` dari
  `.env`, **langsung ganti password** dari menu profil.
- Buat 1 rapat percobaan, upload audio pendek, jalankan proses transkripsi
  + ringkasan — ini memverifikasi Whisper lokal & Ollama benar-benar
  berfungsi (bukan cuma container "running").
- Export notulen ke PDF — ini memverifikasi LibreOffice ter-install benar
  di image (`/api/config` juga melaporkan `pdf_ready: true/false`).

## 7. Backup otomatis

```bash
chmod +x scripts/backup.sh
crontab -e
```

Tambahkan baris (backup tiap hari jam 02:00):

```
0 2 * * * cd /root/notasi-app/notasi-app && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Backup tersimpan di `backups/notasi-backup-<timestamp>.tar.gz` (retensi 14
hari, atur di `scripts/backup.sh`). **Sinkronkan berkala ke storage lain**
(mis. `rclone`/`rsync` ke server/bucket terpisah) — backup yang hanya
tersimpan di VPS yang sama tidak melindungi dari kegagalan disk/VPS.

## 8. Operasional sehari-hari

- Lihat log: `docker compose logs -f app` (atau `ollama` / `caddy`).
- Restart: `docker compose restart app`.
- Update ke versi kode terbaru:
  ```bash
  git pull
  docker compose up -d --build
  ```
- Data (`notasi.db`, `uploads/`, `exports/`) tersimpan di `./data/` di host,
  aman terhadap rebuild/restart container.

## 9. Keterbatasan yang belum ditangani (lihat juga README §10)

- **`/media/bukti`, `/media/materi`, `/media/dokumen`, `/media/rekaman`**
  disajikan publik tanpa autentikasi oleh desain aplikasi saat ini (supaya
  `<img>`/unduhan langsung jalan di browser). Siapa pun yang tahu/menebak
  URL berkas bisa mengaksesnya tanpa login. Kalau berkas rapat Anda
  sensitif, batasi lewat VPN internal/firewall, atau jangan expose domain
  ini ke internet publik sampai endpoint ini diberi autentikasi (perubahan
  kode, di luar scope deployment ini).
- SQLite cocok untuk skala kecil-menengah (satu VPS, bukan multi-instance).
  Untuk banyak pengguna bersamaan, migrasikan ke PostgreSQL lewat
  `DATABASE_URL` (butuh setup service Postgres tambahan, tidak termasuk di
  `docker-compose.yml` ini).
- Penghapusan audio otomatis (`AUDIO_RETENTION_DAYS`) tidak punya
  scheduler bawaan — perlu cron/job terpisah kalau mau diaktifkan.
