SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

## **SPESIFIKASI KEBUTUHAN PERANGKAT LUNAK (** **_SOFTWARE REQUIREMENTS SPECIFICATION_ )** _Dokumen Kebutuhan Sistem_ 

# **APLIKASI NOTASI Notula Otomatis Berbasis** **_Artificial Intelligence_** BPS Kabupaten Sanggau 

Disusun oleh: **Bertolomeus Laksana Jayadri, S.Tr.Stat.** 

NIP. 199909282026031001 Pelaksana — BPS Kabupaten Sanggau 

**<mark>Versi Dokumen</mark>** 1.1 **<mark>Tanggal</mark>** 2026 **<mark>Status</mark>** Rancangan (Draft) 

Halaman 1 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **DAFTAR ISI** 

##### **1. Pendahuluan** 

   - 1.1 Tujuan Penulisan Dokumen 

   - 1.2 Lingkup Masalah 

   - 1.3 Definisi, Akronim, dan Singkatan 

   - 1.4 Referensi 

**2. Deskripsi Umum Sistem** 

   - 2.1 Perspektif Produk 

   - 2.2 Fungsi Utama Produk 

   - 2.3 Karakteristik Pengguna 

   - 2.4 Batasan dan Asumsi 

**3. Kebutuhan Fungsional** 

   - 3.1 Daftar Kebutuhan Fungsional 

   - 3.2 Use Case dan Aktor 

   - 3.3 Alur Proses Utama 

**4. Kebutuhan Non-Fungsional** 

**5. Kebutuhan Antarmuka** 

   - 5.1 Antarmuka Pengguna 

   - 5.2 Antarmuka Perangkat Keras dan Perangkat Lunak 

   - 5.3 Antarmuka Komunikasi 

**6. Kebutuhan Data** 

**7. Kebutuhan Perangkat (Deployment)** 

**8. Penutup** 

Halaman 2 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **1.  Pendahuluan** 

#### **1.1  Tujuan Penulisan Dokumen** 

Dokumen Spesifikasi Kebutuhan Perangkat Lunak (SKPL) ini disusun untuk mendefinisikan kebutuhan sistem aplikasi NOTASI (Notula Otomatis Berbasis _Artificial Intelligence_ ) secara jelas, lengkap, dan terukur. Dokumen ini menjadi acuan bersama antara penyusun, mentor, dan pihak terkait dalam proses pengembangan, pengujian, dan evaluasi aplikasi, sehingga sistem yang dihasilkan sesuai dengan kebutuhan riil unit kerja di BPS Kabupaten Sanggau. 

Secara khusus, dokumen ini bertujuan untuk: (1) menetapkan kebutuhan fungsional dan non-fungsional aplikasi; (2) menjadi dasar perancangan arsitektur dan basis data; serta (3) menjadi tolok ukur dalam pengujian penerimaan (acceptance test) aplikasi. 

#### **1.2  Lingkup Masalah** 

Aplikasi NOTASI adalah perangkat lunak berbasis web yang bertujuan mengotomatiskan proses penyusunan dan pendokumentasian notula rapat. Aplikasi menerima masukan rapat secara fleksibel, yaitu berupa berkas rekaman audio, teks transkrip yang ditempel/diunggah langsung, atau rekaman suara langsung dari peramban (rekam saat siap). Untuk masukan audio, sistem mengubahnya menjadi teks secara otomatis (speech-to-text), lalu meringkasnya menjadi notula terstruktur yang memuat ringkasan pembahasan, keputusan, dan tindak lanjut. Pengguna juga dapat melampirkan materi rapat (berkas PDF, PowerPoint, atau Word) sebagai konteks tambahan agar ringkasan yang dihasilkan lebih kaya dan akurat. Hasilnya dapat disunting melalui editor menyerupai dokumen (Word-like), dilengkapi foto dokumentasi, diekspor ke dokumen Word atau PDF sesuai template resmi, serta tersimpan dalam arsip digital terpusat. 

Lingkup aplikasi dibatasi pada pengelolaan notula rapat internal. Aplikasi tidak menangani penjadwalan rapat, tidak melakukan perekaman audio secara langsung, dan tidak menggantikan sistem persuratan dinas yang telah ada. 

#### **1.3  Definisi, Akronim, dan Singkatan** 

|**Istilah**|**Penjelasan**|
|---|---|
|NOTASI|Nama aplikasi; akronim dari Notula Otomatis Berbasis_Artificial Intelligence_.|
|SKPL / SRS|Spesifikasi Kebutuhan Perangkat Lunak / Software Requirements Specification.|
|Speech-to-Text(STT)|Teknologiyangmengubah suara/audio menjadi teks secara otomatis.|
|LLM|Large Language Model; model bahasa AI yang digunakan untuk meringkas<br>transkrip.|
|Transkrip|Hasilpengubahan rekaman audio rapat menjadi teks.|
|Notula|Catatan resmi hasil rapat yang memuat pembahasan, keputusan, dan tindak<br>lanjut.|
|Materi Rapat|Berkas pendukung rapat (PDF/PPT/Word) yang dijadikan konteks tambahan<br>bagiperingkasan AI.|
|Mode AI|Pilihanpenyedia AI: demo(contoh),gratis/lokal, atau berbayar(daring).|
|ArsipDigital|Kumpulan notulayangtersimpan secara elektronik dan dapat ditelusuri.|
|API|Application Programming Interface; antarmuka pertukaran data antar-perangkat<br>lunak.|



_Tabel 1.1 Definisi, Akronim, dan Singkatan_ 

Halaman 3 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

#### **1.4  Referensi** 

- Peraturan LAN RI tentang Pelatihan Dasar Calon PNS dan aktualisasi nilai-nilai dasar ASN BerAKHLAK. 

- Kaidah umum penyusunan Spesifikasi Kebutuhan Perangkat Lunak (mengacu pada struktur IEEE Std 830). 

- Template notula kegiatan yang berlaku di BPS Kabupaten Sanggau. 

Halaman 4 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **2.  Deskripsi Umum Sistem** 

#### **2.1  Perspektif Produk** 

NOTASI merupakan produk perangkat lunak mandiri (standalone) berbasis web yang dijalankan pada peramban. Sistem terdiri atas dua bagian utama, yaitu antarmuka pengguna (frontend) dan layanan server (backend). Backend mengorkestrasi beberapa komponen inti: mesin speech-to-text untuk transkripsi, model bahasa (LLM) untuk peringkasan, pengekstrak teks materi rapat, dan basis data untuk penyimpanan. Sistem dirancang fleksibel melalui tiga mode AI yang dapat dipindah dengan mudah melalui menu Pengaturan: mode demo (memakai data contoh, tanpa biaya dan tanpa kunci API), mode gratis/lokal (mesin AI berjalan di server sendiri, mis. faster-whisper dan Ollama, tanpa biaya lisensi), dan mode berbayar (memakai layanan daring seperti OpenAI). Pemilihan mode disesuaikan dengan kebijakan keamanan data dan anggaran instansi. 

#### **2.2  Fungsi Utama Produk** 

Secara garis besar, fungsi utama aplikasi NOTASI adalah sebagai berikut. 

- Autentikasi pengguna (login) dengan tiga tingkat hak akses: administrator, notulis, dan pegawai. 

- Masukan rapat fleksibel: unggah berkas audio, tempel/unggah teks transkrip, atau rekam suara langsung dari peramban. 

- Pelampiran materi rapat (PDF/PPT/Word) sebagai konteks tambahan untuk peringkasan. 

- Transkripsi otomatis rekaman menjadi teks (untuk masukan audio). 

- Peringkasan otomatis menjadi ringkasan pembahasan, keputusan, dan tindak lanjut, dengan mempertimbangkan materi rapat bila dilampirkan. 

- Penyuntingan hasil melalui editor menyerupai dokumen (Word-like) beserta metadata rapat. 

- Pengunggahan foto dokumentasi kegiatan. 

- Ekspor notula ke berkas Word dan PDF sesuai template resmi. 

- Pengarsipan digital serta pencarian dan pengelolaan (CRUD) notula. 

- Pengaturan mode AI (demo/gratis/berbayar) yang mudah dipindah tanpa mengubah kode. 

- Pemantauan kemajuan proses AI secara waktu nyata (progress). 

#### **2.3  Karakteristik Pengguna** 

|**Peran**|**Hak Akses**|**Karakteristik**|
|---|---|---|
|Administrator|CRUD penuh atas notula dan<br>pengaturan; kelola akun pengguna|Mengelola sistem, akun, dan mode AI;<br>memiliki seluruh kewenangan notulis<br>ditambah manajemenpengguna.|
|Notulis|CRUD notula (buat, baca, sunting,<br>hapus)|Pengguna aktif penyusun notula;<br>membuat, menyunting, mengekspor, dan<br>mengelola notula.|
|Pegawai (User)|Read-only (hanya baca notula & arsip)|Pengguna yang membutuhkan akses<br>melihat dan mengunduh notula, tanpa<br>kewenangan mengubah data.|



Halaman 5 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

_Tabel 2.1 Karakteristik Pengguna dan Hak Akses (Role-Based Access Control)_ 

#### **2.4  Batasan dan Asumsi** 

- Aplikasi diakses melalui peramban modern (Chrome, Edge, Firefox) pada jaringan internal instansi. 

- Kualitas transkripsi bergantung pada kejernihan audio rekaman rapat. 

- Rekaman rapat diasumsikan berbahasa Indonesia. 

- Masukan teks langsung tidak melalui tahap transkripsi, sehingga prosesnya lebih cepat karena langsung diringkas. 

- Kualitas ekstraksi teks materi bergantung pada jenis berkas; materi berupa hasil pindai (gambar) mungkin memerlukan OCR terpisah. 

- Ekspor PDF mensyaratkan tersedianya LibreOffice pada server; ekspor Word tidak memerlukan perangkat lunak tambahan. 

- Hasil ringkasan AI bersifat bantuan; keputusan akhir atas isi notula tetap diverifikasi oleh notulis. 

Halaman 6 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **3.  Kebutuhan Fungsional** 

#### **3.1  Daftar Kebutuhan Fungsional** 

Kebutuhan fungsional (SRS-F) menjelaskan layanan yang harus disediakan sistem. Setiap kebutuhan diberi kode unik untuk keperluan penelusuran. 

|**Kode**|**Kebutuhan Fungsional**|**Deskripsi**|**Prioritas**|
|---|---|---|---|
|SRS-F-01|Autentikasi & RBAC|Sistem menyediakan login dan<br>mengatur hak akses tiga peran:<br>administrator (CRUD penuh + kelola<br>pengguna), notulis (CRUD notula),<br>danpegawai(read-only).|Tinggi|
|SRS-F-02|Manajemen pengguna|Administrator dapat menambah,<br>mengubah, menetapkan peran, dan<br>menonaktifkan akunpengguna.|Tinggi|
|SRS-F-03|Masukan rapat fleksibel|Pengguna dapat memilih sumber<br>notula: (a) unggah berkas audio, (b)<br>tempel/unggah teks transkrip, atau<br>(c) rekam suara langsung dari<br>peramban(mulai saat siap).|Tinggi|
|SRS-F-04|Input metadata rapat|Pengguna mengisi topik, tanggal,<br>tempat, waktu, pimpinan, notulis,<br>danpeserta rapat.|Tinggi|
|SRS-F-05|Lampiran materi rapat|Pengguna dapat melampirkan<br>materi rapat (PDF/PPT/Word);<br>sistem mengekstrak teksnya<br>sebagai konteks tambahan bagi<br>peringkasan.|Sedang|
|SRS-F-06|Transkripsi otomatis (STT)|Untuk masukan audio, sistem<br>mengubah rekaman menjadi teks<br>secara otomatis; audio panjang<br>diproses paralel (chunking) agar<br>lebih cepat.|Tinggi|
|SRS-F-07|Peringkasan otomatis (LLM)|Sistem menghasilkan ringkasan<br>pembahasan, keputusan, dan tindak<br>lanjut beserta penanggung jawab,<br>dengan turut mempertimbangkan<br>materi rapat bila ada.|Tinggi|
|SRS-F-08|Pengaturan mode AI|Pengguna (administrator) dapat<br>memindah mode AI antara demo,<br>gratis/lokal, dan berbayar dengan<br>mudah melalui menu Pengaturan.|Tinggi|
|SRS-F-09|Pemantauan progres|Sistem menampilkan kemajuan<br>proses AI (0–100%) dan berjalan di<br>latar belakang.|Sedang|
|SRS-F-10|Editor menyerupai dokumen|Pengguna menyunting notula<br>melalui editor yang tampil<br>menyerupai dokumen Word (Word-<br>like), mencakup transkrip,<br>ringkasan, keputusan, tindak lanjut,<br>dan metadata.|Tinggi|
|SRS-F-11|Unggah foto dokumentasi|Pengguna mengunggah foto<br>kegiatan yang otomatis disisipkan<br>ke dokumen hasil ekspor.|Sedang|
|SRS-F-12|Ekspor dokumen|Sistem mengekspor notula ke Word<br>dan PDF sesuai template resmi<br>instansi.|Tinggi|
|SRS-F-13|Arsip & pencarian|Sistem menyimpan notula dalam<br>arsip digital serta menyediakan<br>fungsi lihat, cari, ubah, dan hapus<br>sesuai hak akses.|Tinggi|
|SRS-F-14|Cetak & bagikan|Pengguna dapat mencetak notula<br>dan membagikannya (mis.<br>tautan/berkas).|Rendah|



Halaman 7 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

|**Kode**|**Kebutuhan Fungsional**|**Deskripsi**|**Prioritas**|
|---|---|---|---|
|SRS-F-15|Konfigurasi template|Template dokumen (kop, urutan<br>bagian, pemisah halaman) dapat<br>diubah tanpa mengubah kode.|Sedang|



_Tabel 3.1 Daftar Kebutuhan Fungsional_ 

#### **3.2  Use Case dan Aktor** 

Terdapat tiga aktor, yaitu Administrator (pengelola sistem dan pengguna), Notulis (penyusun 

notula), dan Pegawai (pembaca notula). Ringkasan use case disajikan pada tabel berikut. 

|**Use Case**|**Aktor**|**Deskripsi Singkat**|
|---|---|---|
|Login|Semuaperan|Masuk ke sistem sesuai hak akses.|
|Buat Notula|Admin, Notulis|Membuat notula dari audio, teks, atau rekaman<br>langsung.|
|Lampirkan Materi|Admin, Notulis|Menambahkan berkas materi (PDF/PPT/Word)<br>sebagai konteks ringkasan.|
|Sunting Notula|Admin, Notulis|Menyunting isi dan metadata melalui editor<br>menyerupai dokumen.|
|Unggah Dokumentasi|Admin, Notulis|Menambahkan foto bukti kegiatan.|
|Ekspor / Cetak|Admin, Notulis|Mengekspor ke Word/PDF atau mencetak.|
|Lihat / Unduh Notula|Semua peran|Membaca dan mengunduh notula (pegawai bersifat<br>read-only).|
|Kelola Arsip|Admin, Notulis|Melihat, mencari, mengubah, menghapus notula.|
|Atur Mode AI|Admin|Memindah mode AI: demo,gratis/lokal, atau berbayar.|
|Kelola Pengguna|Admin|Menambah/menonaktifkan akun dan menetapkan<br>peran.|



_Tabel 3.2 Ringkasan Use Case dan Aktor_ 

#### **3.3  Alur Proses Utama** 

Alur proses pembuatan notula (skenario utama) berlangsung sebagai berikut. 

1. Pengguna login, lalu mengisi metadata rapat dan memilih sumber notula: unggah audio, tempel/unggah teks, atau rekam langsung. 

2. Pengguna dapat melampirkan materi rapat (PDF/PPT/Word) sebagai konteks tambahan (opsional). 

3. Untuk masukan audio, sistem menjalankan transkripsi otomatis (STT) di latar belakang sambil menampilkan progres; untuk masukan teks, tahap ini dilewati. 

4. Sistem meringkas transkrip menjadi pembahasan, keputusan, dan tindak lanjut (LLM), dengan mempertimbangkan materi rapat bila dilampirkan. 

5. Pengguna meninjau dan menyunting melalui editor menyerupai dokumen, serta mengunggah foto dokumentasi. 

6. Pengguna mengekspor notula ke Word/PDF; sistem menyimpannya ke arsip digital. 

Halaman 8 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **4.  Kebutuhan Non-Fungsional** 

Kebutuhan non-fungsional (SRS-NF) menjelaskan batasan mutu dan karakteristik operasional sistem. 

|**Kode**|**Aspek**|**Kebutuhan**|
|---|---|---|
|SRS-NF-01|Kegunaan (Usability)|Antarmuka profesional, minimalis, dan bernuansa biru yang<br>konsisten; berbahasa Indonesia; dapat digunakan pegawai<br>dengan literasi digital dasar tanpa pelatihan khusus yang<br>panjang.|
|SRS-NF-02|Kinerja (Performance)|Proses berjalan di latar belakang sehingga pengguna dapat<br>berpindah halaman; kemajuan proses ditampilkan secara<br>berkala.|
|SRS-NF-03|Keamanan (Security)|Akses dilindungi autentikasi berbasis token; kata sandi disimpan<br>dalam bentuk ter-hash; hak akses dibedakanperperan.|
|SRS-NF-04|Keandalan (Reliability)|Proses yang gagal dapat diulang tanpa mengunggah ulang<br>audio; kegagalan komponen kosmetik tidak membatalkan hasil<br>utama.|
|SRS-NF-05|Ketersediaan (Availability)|Dapat dijalankan pada server internal instansi dan diakses<br>selamajam kerja melaluijaringan lokal.|
|SRS-NF-06|Kompatibilitas|Berjalan pada peramban modern; mendukung berkas audio<br>umum (MP3, WAV, M4A), masukan teks, serta materi berformat<br>PDF, PPT/PPTX, dan DOC/DOCX.|
|SRS-NF-07|Pemeliharaan<br>(Maintainability)|Template dokumen dan pilihan mesin AI dapat dikonfigurasi<br>tanpa mengubah kodeprogram.|
|SRS-NF-08|Portabilitas|Basis data dapat berupa SQLite untuk skala kecil dan dapat<br>dimigrasi ke basis data lain untuk skala lebih besar.|
|SRS-NF-09|Privasi Data|Opsi mesin AI lokal memungkinkan seluruh pemrosesan<br>dilakukan di lingkungan internal tanpa mengirim data keluar.|



_Tabel 4.1 Daftar Kebutuhan Non-Fungsional_ 

Halaman 9 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **5.  Kebutuhan Antarmuka** 

#### **5.1  Antarmuka Pengguna** 

Antarmuka pengguna berbasis web dengan gaya visual profesional dan minimalis bernuansa biru (blue tone) yang konsisten, mengutamakan keterbacaan dan kemudahan penggunaan. Antarmuka terdiri atas halaman-halaman berikut. 

- **Halaman Login** — autentikasi pengguna sesuai peran. 

- **Dashboard** — ringkasan jumlah rapat, notula bulan ini, total arsip, dan grafik per bulan. 

- **Buat Notula** — pemilihan sumber (audio / teks / rekam langsung), formulir metadata, pemilihan peserta (dengan pencarian), serta pelampiran materi rapat. 

- **Perekam Suara** — antarmuka rekam langsung di peramban dengan tombol mulai/berhenti (mulai saat siap). 

- **Proses** — lingkaran progres 0–100% dengan keterangan tahapan. 

- **Editor (Word-like)** — penyuntingan menyerupai dokumen: transkrip, ringkasan, keputusan, tindak lanjut, dan foto dokumentasi. 

- **Pratinjau** — tampilan notula berformat resmi untuk dicetak/dibagikan. 

- **Arsip** — daftar notula dengan aksi sesuai hak akses (lihat, sunting, ekspor, hapus). 

- **Manajemen Pengguna** — khusus administrator: kelola akun dan peran. 

- **Pengaturan** — pemindahan mode AI (demo/gratis/berbayar), status mesin AI, dan akun. 

#### **5.2  Antarmuka Perangkat Keras dan Perangkat Lunak** 

- **Perangkat keras:** server/komputer dengan RAM memadai (disarankan minimal 8 GB bila memakai mesin AI lokal); perangkat klien berupa komputer dengan peramban. 

- **Perangkat lunak:** lingkungan Python untuk backend; peramban modern untuk frontend; LibreOffice untuk ekspor PDF; serta mesin AI (layanan daring atau lokal). 

#### **5.3  Antarmuka Komunikasi** 

Komunikasi antara frontend dan backend menggunakan protokol HTTP melalui antarmuka REST API dalam format JSON. Bila menggunakan layanan AI daring, komunikasi ke penyedia dilakukan melalui API terenkripsi (HTTPS). Bila menggunakan mesin AI lokal, komunikasi berlangsung di dalam jaringan internal. 

Halaman 10 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **6.  Kebutuhan Data** 

Sistem menyimpan data pada basis data relasional. Struktur utama tabel-tabel yang dibutuhkan disajikan pada tabel berikut. 

|**Tabel**|**Kolom Utama**|**Keterangan**|
|---|---|---|
|users|`id, nama, username,`<br>`password_hash, role`|Data akun; role bernilai admin, notulis,<br>atau pegawai.|
|pegawai|`id, nama, jabatan, urutan`|Daftar pegawai untuk pilihan pimpinan,<br>notulis, danpeserta.|
|meetings|`id, topik, tanggal, tempat,`<br>`waktu, pimpinan, notulis,`<br>`peserta, input_mode,`<br>`sumber_teks, status, progress`|Metadata, mode masukan<br>(audio/teks/rekam), dan status setiap<br>rapat.|
|materials|`id, meeting_id, file_path, tipe,`<br>`teks_ekstrak`|Materi rapat (PDF/PPT/Word) beserta<br>teks hasil ekstraksi untuk konteks<br>ringkasan.|
|transcripts|`id, meeting_id, teks_transkripsi`|Hasil transkripsi (dari STT) atau teks yang<br>dimasukkan langsung.|
|summaries|`id, meeting_id, ringkasan,`<br>`keputusan`|Hasil ringkasan dan keputusan dari LLM.|
|action_items|`id, meeting_id, deskripsi,`<br>`penanggung_jawab, deadline,`<br>`status`|Daftar tindak lanjut hasil rapat.|
|documentation|`id, meeting_id, file_path,`<br>`keterangan`|Foto bukti dokumentasi kegiatan.|
|archives|`id, meeting_id, file,`<br>`tanggal_ekspor`|Riwayat berkas hasil ekspor (Word/PDF).|



_Tabel 6.1 Struktur Data Utama Aplikasi NOTASI_ 

Relasi antar-tabel bersifat satu rapat (meetings) memiliki satu transkrip, satu ringkasan, serta beberapa tindak lanjut, foto dokumentasi, dan riwayat arsip. Penghapusan sebuah rapat akan menghapus seluruh data terkait secara berantai (cascade). 

Halaman 11 

SKPL Aplikasi NOTASI — BPS Kabupaten Sanggau 

### **7.  Kebutuhan Perangkat (Deployment)** 

Aplikasi NOTASI dirancang agar dapat dijalankan pada satu server internal instansi. Konfigurasi minimum dan pilihan mesin AI diringkas sebagai berikut. 

|**Komponen**|**Spesifikasi / Pilihan**|
|---|---|
|Sistem Operasi|Windows atau Linux(server internal instansi).|
|Backend|Layanan Python(FastAPI) yang juga menyajikan frontend.|
|Basis Data|SQLite(skala kecil)atau basis data relasional lain(skala lebih besar).|
|Mesin STT|Layanan daring (OpenAI Whisper) atau lokal (faster-whisper) — gratis, tanpa<br>API key.|
|Mesin LLM|Layanan daring (OpenAI) atau lokal (Ollama, mis. Llama 3/Mistral) — gratis,<br>tanpa API key.|
|Ekspor PDF|Membutuhkan LibreOffice(gratis)terpasangdi server.|
|Akses|Melaluiperambanpadajaringan internal instansi.|



_Tabel 7.1 Kebutuhan Perangkat dan Pilihan Penyebaran_ 

Fleksibilitas pilihan mesin AI memungkinkan instansi memilih konfigurasi yang sepenuhnya 

lokal (tanpa biaya lisensi dan tanpa mengirim data keluar) demi menjaga kerahasiaan pembahasan rapat, atau memakai layanan daring bila mengutamakan kecepatan dan kemudahan. 

### **8.  Penutup** 

Tabel berikut merangkum penyempurnaan kebutuhan pada versi dokumen ini (v1.1) dibandingkan versi sebelumnya, sebagai hasil konsultasi dan pengembangan lebih lanjut. 

|**Fitur/Penyempurnaan(v1.1)**|**Kebutuhan Terkait**|
|---|---|
|Masukan rapat fleksibel: audio, teks,<br>atau rekam langsung|SRS-F-03, SRS-F-06|
|Lampiran materi rapat (PDF/PPT/Word)<br>sebagai konteks ringkasan|SRS-F-05, SRS-F-07|
|Pengaturan mode AI<br>(demo/gratis/berbayar) yang mudah<br>dipindah|SRS-F-08|
|Tiga peran pengguna: admin (CRUD),<br>notulis(CRUD),pegawai(read-only)|SRS-F-01, SRS-F-02|
|Editor penyuntingan menyerupai<br>dokumen(Word-like)|SRS-F-10|
|Antarmuka profesional, minimalis, tone<br>biru|SRS-NF-01|



_Tabel 8.1 Ringkasan Penyempurnaan pada Versi 1.1_ 

Dokumen Spesifikasi Kebutuhan Perangkat Lunak ini memuat kebutuhan fungsional, non- 

fungsional, antarmuka, data, dan penyebaran aplikasi NOTASI sebagai dasar pengembangan yang terarah dan terukur. Dokumen bersifat hidup (living document) dan dapat disempurnakan seiring masukan dari mentor dan pengguna selama tahapan aktualisasi. Dengan terpenuhinya kebutuhan yang tercantum, aplikasi NOTASI diharapkan mampu mempercepat penyusunan serta menertibkan pendokumentasian notula rapat, sekaligus mendukung penguatan Manajemen ASN dan Smart ASN di lingkungan BPS Kabupaten Sanggau. 

Halaman 12 

