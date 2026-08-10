"""
Data pegawai BPS Kabupaten Sanggau, dibersihkan dari berkas Daftar_Pegawai.md
yang diunggah pengguna (tabel markdown dengan pembungkusan baris <br> dirapikan
kembali menjadi nama & jabatan yang utuh).

Data ini di-seed ke tabel `pegawai` saat aplikasi pertama kali dijalankan,
lalu dipakai untuk mengisi pilihan "Pimpinan Rapat", "Notulis", dan
"Peserta Rapat" pada form pembuatan notulensi (menggantikan isian teks bebas).
"""

PEGAWAI_SEED = [
    ("Hakim Azizi, S.ST., MM.", "Kepala BPS Kabupaten Sanggau"),
    ("Muhamad Zainuri, SST", "Kepala Subbagian Umum"),
    ("Vinanda Sonya Permatasari, A.Md.Stat.", "Statistisi Terampil"),
    ("Jhon Kenedy Simarmata, SST., M.Ak.", "Statistisi Ahli Muda"),
    ("Arini Larasati, SST", "Statistisi Ahli Pertama"),
    ("Dedi Anggriawan, SST", "Statistisi Ahli Pertama"),
    ("Sunggul Atalia, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Aryo Joko Prakoso, S.Si.", "Statistisi Ahli Pertama"),
    ("Diana Putri Silitonga, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Divia Angelina, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Dewi Retno Oscarini, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Natalia Panjaitan, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Muhammad Indrayadi", "Statistisi Penyelia"),
    ("Ello Vanly Saragih, S.Si", "Statistisi Ahli Pertama"),
    ("Rado Simarmata, A.Md.T.", "Statistisi Terampil"),
    ("Zulkifli", "Pengolah Data"),
    ("Zulmawan", "Pengolah Data"),
    ("Ade Rajuni", "Pengolah Data"),
    ("Willy Pradana Putra, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Azzahra Zauza Inniswa Rahmadhana, S.Tr.Stat.", "Statistisi Ahli Pertama"),
    ("Yudistira Elton Jhon, S.Tr.Stat.", "Pranata Komputer Ahli Pertama"),
    ("Riofebri Prasetia, S.Tr.Stat.", "Pranata Komputer Ahli Pertama"),
    ("Trison Cristian Butar-Butar, A.Md.Stat.", "Statistisi Terampil"),
    ("Bertolomeus Laksana Jayadri", "Staf BPS Kabupaten Sanggau"),
    ("Muhammad Adi Williansyah, A.Md", "Pranata Komputer Terampil"),
    ("Irfan Hidayat", "Operator Layanan Operasional"),
    ("Erna Marningsih", "Operator Layanan Operasional"),
    ("Kusman Kosmos", "Operator Layanan Operasional"),
    ("Syahrul Wahyudi", "Operator Layanan Operasional"),
]
