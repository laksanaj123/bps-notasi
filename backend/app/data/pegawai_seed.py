"""
Data pegawai BPS Kabupaten Sanggau, dibersihkan dari berkas Daftar_Pegawai.md
yang diunggah pengguna (tabel markdown dengan pembungkusan baris <br> dirapikan
kembali menjadi nama & jabatan yang utuh).

Data ini di-seed ke tabel `users` (role pegawai) saat aplikasi pertama kali
dijalankan, lalu dipakai untuk mengisi pilihan "Pimpinan Rapat", "Notulis", dan
"Peserta Rapat" pada form pembuatan rapat/notula (menggantikan isian teks bebas).

Setiap entri: (nama, jabatan, tim). `tim` = salah satu dari
Umum / IPDS / Produksi / Distribusi / Neraca / Sosial, atau gabungan "X/Y" untuk
pegawai yang merangkap 2 tim (dia ikut kalau rapat internal tim X MAUPUN tim Y).
`tim=None` untuk Kepala BPS & operator layanan yang tidak masuk struktur tim
teknis. Dipakai tombol "Pilih Rapat Tim" di langkah Peserta (lihat
routers/rapat.py `_users_in_tim` / endpoint `/{rapat_id}/peserta/tim`).
"""

PEGAWAI_SEED = [
    ("Hakim Azizi, S.ST., MM.", "Kepala BPS Kabupaten Sanggau", None, "081225069065"),
    ("Muhamad Zainuri, SST", "Kepala Subbagian Umum", "Umum", "081225069065"),
    ("Vinanda Sonya Permatasari, A.Md.Stat.", "Statistisi Terampil", "Umum", "081225069065"),
    ("Jhon Kenedy Simarmata, SST., M.Ak.", "Statistisi Ahli Muda", "Distribusi", "081225069065"),
    ("Arini Larasati, SST", "Statistisi Ahli Muda", "Neraca", "081225069065"),
    ("Dedi Anggriawan, SST", "Statistisi Ahli Pertama", "Produksi", "081225069065"),
    ("Sunggul Atalia, S.Tr.Stat.", "Statistisi Ahli Pertama", "Sosial", "081225069065"),
    ("Aryo Joko Prakoso, S.Si.", "Statistisi Ahli Pertama", "Sosial", "081225069065"),
    ("Diana Putri Silitonga, S.Tr.Stat.", "Statistisi Ahli Pertama", "Distribusi/Umum", "081225069065"),
    ("Divia Angelina, S.Tr.Stat.", "Statistisi Ahli Pertama", "Distribusi", "081225069065"),
    ("Dewi Retno Oscarini, S.Tr.Stat.", "Statistisi Ahli Pertama", "Distribusi", "081225069065"),
    ("Natalia Panjaitan, S.Tr.Stat.", "Statistisi Ahli Pertama", "Sosial", "081225069065"),
    ("Muhammad Indrayadi", "Statistisi Penyelia", "Produksi", "081225069065"),
    ("Ello Vanly Saragih, S.Si", "Statistisi Ahli Pertama", "Produksi/Umum", "081225069065"),
    ("Rado Simarmata, A.Md.T.", "Statistisi Terampil", "Sosial/Umum", "081225069065"),
    ("Zulkifli", "Pengolah Data", "Distribusi", "081225069065"),
    ("Zulmawan", "Pengolah Data", "Sosial", "081225069065"),
    ("Ade Rajuni", "Pengolah Data", "Neraca", "081225069065"),
    ("Willy Pradana Putra, S.Tr.Stat.", "Statistisi Ahli Pertama", "Produksi/Umum", "081225069065"),
    ("Azzahra Zauza Inniswa Rahmadhana, S.Tr.Stat.", "Statistisi Ahli Pertama", "Neraca/Umum", "081225069065"),
    ("Yudistira Elton Jhon, S.Tr.Stat.", "Pranata Komputer Ahli Pertama", "IPDS", "081225069065"),
    ("Riofebri Prasetia, S.Tr.Stat.", "Pranata Komputer Ahli Pertama", "IPDS", "081225069065"),
    ("Trison Cristian Butar-Butar, A.Md.Stat.", "Statistisi Terampil", "Produksi", "081225069065"),
    ("Bertolomeus Laksana Jayadri", "Staf BPS Kabupaten Sanggau", "IPDS", "081225069065"),
    ("Muhammad Adi Williansyah, A.Md", "Pranata Komputer Terampil", "IPDS/Umum", "081225069065"),
    ("Irfan Hidayat", "Operator Layanan Operasional", None, "081225069065"),
    ("Erna Marningsih", "Operator Layanan Operasional", None, "081225069065"),
    ("Kusman Kosmos", "Operator Layanan Operasional", None, "081225069065"),
    ("Syahrul Wahyudi", "Operator Layanan Operasional", None, "081225069065"),
]
