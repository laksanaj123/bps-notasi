"""
Membuat dokumen notulensi (.docx) mengikuti format resmi
'template-notule-kegiatan.md' yang disediakan BPS Kabupaten Sanggau:
kop surat berulang di setiap halaman, tabel info rapat, tabel peserta,
narasi pendahuluan, pembahasan & keputusan, tabel tindak lanjut, blok
tanda tangan (Kepala & Notulis), serta lampiran foto dokumentasi kegiatan.
"""
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from ..config import settings
from ..utils.indo_date import (
    format_tanggal_lengkap, format_tanggal_singkat, format_jam, hitung_durasi,
)

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "bps_logo.png"
# Template Word resmi BPS Kabupaten Sanggau (Template_Notula_Rapat.docx),
# diubah jadi versi berplaceholder ({{token}}) lewat skrip satu-kali - lihat
# build_notula_from_template() di bawah. Dipakai supaya hasil ekspor
# persis meniru format Word asli (font/tabel/kop surat resminya sendiri),
# bukan rekonstruksi ulang lewat python-docx seperti build_notulensi_docx().
NOTULA_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "notula_template.docx"


def _add_letterhead(doc: Document):
    """Kop surat, dipasang sebagai header halaman agar berulang otomatis
    di setiap halaman - logo BPS, nama instansi, dan alamat, sesuai
    format resmi notula BPS Kabupaten Sanggau."""
    header = doc.sections[0].header
    p0 = header.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if LOGO_PATH.exists():
        p0.add_run().add_picture(str(LOGO_PATH), height=Cm(1.6))

    p1 = header.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run1 = p1.add_run(settings.NAMA_INSTANSI)
    run1.bold = True
    run1.italic = True
    run1.font.size = Pt(12)

    p2 = header.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(settings.ALAMAT_INSTANSI)
    run2.font.size = Pt(8)

    # garis pemisah tipis di bawah kop
    p3 = header.add_paragraph()
    p3.paragraph_format.space_after = Pt(4)
    run3 = p3.add_run("_" * 95)
    run3.font.size = Pt(6)


def _info_table(doc: Document, meeting):
    table = doc.add_table(rows=2, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    cells = table.rows[0].cells
    cells[0].text = "Unit Kerja"
    cells[1].text = meeting.unit_kerja or settings.UNIT_KERJA_DEFAULT
    cells[2].text = "Tanggal"
    cells[3].text = format_tanggal_singkat(meeting.tanggal)

    cells = table.rows[1].cells
    cells[0].text = "Topik"
    cells[1].text = meeting.judul_rapat
    cells[2].text = "Tempat"
    cells[3].text = meeting.lokasi or "-"

    for row in table.rows:
        row.cells[0].paragraphs[0].runs[0].bold = True
        row.cells[2].paragraphs[0].runs[0].bold = True
    return table


def _peserta_table(doc: Document, peserta_list):
    doc.add_paragraph("")
    heading = doc.add_paragraph()
    run = heading.add_run("Peserta Rapat")
    run.bold = True

    rows_needed = (len(peserta_list) + 1) // 2 if peserta_list else 1
    table = doc.add_table(rows=rows_needed + 1, cols=4)
    table.style = "Table Grid"

    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Nama", "Jabatan", "Nama", "Jabatan"
    for c in hdr:
        c.paragraphs[0].runs[0].bold = True

    for i in range(rows_needed):
        row = table.rows[i + 1].cells
        left = peserta_list[i * 2] if i * 2 < len(peserta_list) else None
        right = peserta_list[i * 2 + 1] if i * 2 + 1 < len(peserta_list) else None
        row[0].text = left.nama if left else ""
        row[1].text = left.jabatan if left else ""
        row[2].text = right.nama if right else ""
        row[3].text = right.jabatan if right else ""
    return table


def build_pendahuluan_text(meeting, pimpinan) -> str:
    tanggal_lengkap = format_tanggal_lengkap(meeting.tanggal)
    jam_mulai = format_jam(meeting.waktu_mulai)
    jam_selesai = format_jam(meeting.waktu_selesai)
    durasi = hitung_durasi(meeting.waktu_mulai, meeting.waktu_selesai)
    pimpinan_text = f"{pimpinan.nama} ({pimpinan.jabatan})" if pimpinan else "pimpinan rapat"

    parts = [
        f"Pada hari {tanggal_lengkap}",
    ]
    if meeting.waktu_mulai:
        parts[0] += f", pukul {jam_mulai}"
    text = (
        f"{parts[0]}, telah dilaksanakan {meeting.judul_rapat}. "
        f"Rapat ini dipimpin langsung oleh {pimpinan_text}."
    )
    if durasi != "-":
        text += f" Kegiatan rapat berlangsung selama {durasi}"
        if meeting.waktu_selesai:
            text += f" dan berakhir pada pukul {jam_selesai}"
        text += "."
    return text


def _pendahuluan_paragraph(doc: Document, meeting, pimpinan, pendahuluan_text=None):
    doc.add_heading("Pendahuluan", level=2)
    doc.add_paragraph(pendahuluan_text or build_pendahuluan_text(meeting, pimpinan))


def _pembahasan_section(doc: Document, ringkasan, keputusan):
    doc.add_heading("Pembahasan Rapat", level=2)
    if ringkasan:
        for i, point in enumerate(ringkasan, start=1):
            doc.add_paragraph(f"{i}. {point}")
    else:
        doc.add_paragraph("Tidak ada poin pembahasan yang tercatat.")

    doc.add_heading("Keputusan Rapat", level=2)
    if keputusan:
        for point in keputusan:
            doc.add_paragraph(point, style="List Bullet")
    else:
        doc.add_paragraph("Tidak ada keputusan yang tercatat.")


def _pembahasan_ringkas_section(doc: Document, ringkasan):
    doc.add_heading("Pembahasan Rapat", level=2)
    if ringkasan:
        for i, point in enumerate(ringkasan, start=1):
            doc.add_paragraph(f"{i}. {point}")
    else:
        doc.add_paragraph("Tidak ada poin pembahasan yang tercatat.")


def _tanya_jawab_section(doc: Document, pertanyaan_jawaban):
    doc.add_heading("Pertanyaan dan Jawaban", level=2)
    if not pertanyaan_jawaban:
        doc.add_paragraph("Tidak ada tanya jawab yang tercatat.")
        return
    for item in pertanyaan_jawaban:
        p_t = doc.add_paragraph()
        p_t.add_run(f"T: {item.get('pertanyaan', '')}").bold = True
        doc.add_paragraph(f"J: {item.get('jawaban', '')}")


def _tindak_lanjut_table(doc: Document, tindak_lanjut):
    doc.add_heading("Tindak Lanjut", level=2)
    if not tindak_lanjut:
        doc.add_paragraph("Tidak ada tindak lanjut yang teridentifikasi.")
        return
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Action Item", "Penanggung Jawab", "Deadline", "Status"
    for c in hdr:
        c.paragraphs[0].runs[0].bold = True
    for item in tindak_lanjut:
        r = table.add_row().cells
        r[0].text = item["deskripsi"]
        r[1].text = item.get("penanggung_jawab") or "-"
        r[2].text = item.get("deadline") or "-"
        r[3].text = item.get("status") or "Pending"


def _tanda_tangan(doc: Document, meeting, kepala, notulis):
    doc.add_paragraph("")
    p = doc.add_paragraph(f"{(meeting.unit_kerja or settings.UNIT_KERJA_DEFAULT).split(' ')[-1]}, "
                           f"{format_tanggal_singkat(meeting.tanggal)}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    table = doc.add_table(rows=4, cols=2)
    table.autofit = True
    left_lines = ["Mengetahui,", f"Kepala {meeting.unit_kerja or settings.UNIT_KERJA_DEFAULT}", "", ""]
    right_lines = ["", "Notulis:", "", ""]

    for i, line in enumerate(left_lines):
        table.rows[i].cells[0].paragraphs[0].add_run(line)
    for i, line in enumerate(right_lines):
        table.rows[i].cells[1].paragraphs[0].add_run(line)

    # ruang tanda tangan
    for _ in range(2):
        table.add_row()

    nama_row = table.add_row().cells
    kepala_run = nama_row[0].paragraphs[0].add_run(kepala.nama if kepala else "-")
    kepala_run.bold = True
    kepala_run.underline = True
    notulis_run = nama_row[1].paragraphs[0].add_run(notulis.nama if notulis else "-")
    notulis_run.bold = True
    notulis_run.underline = True


def _dokumentasi_section(doc: Document, meeting, dokumentasi_files):
    doc.add_page_break()
    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading.add_run(f"DOKUMENTASI KEGIATAN {meeting.judul_rapat.upper()}")
    run.bold = True
    run.font.size = Pt(13)

    if not dokumentasi_files:
        p = doc.add_paragraph("Tidak ada bukti dokumentasi yang diunggah untuk kegiatan ini.")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return

    # tampilkan foto 2 kolom per baris menggunakan tabel tanpa border
    photos = list(dokumentasi_files)
    rows_needed = (len(photos) + 1) // 2
    table = doc.add_table(rows=rows_needed, cols=2)
    idx = 0
    for r in range(rows_needed):
        for c in range(2):
            if idx >= len(photos):
                break
            cell = table.rows[r].cells[c]
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            try:
                run.add_picture(str(photos[idx]["path"]), width=Cm(7))
            except Exception:
                para.add_run("[Gagal memuat gambar]")
            if photos[idx].get("keterangan"):
                cap = cell.add_paragraph(photos[idx]["keterangan"])
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.runs[0].italic = True
                cap.runs[0].font.size = Pt(9)
            idx += 1


def build_notulensi_docx(meeting, transcript_text, ringkasan, keputusan, tindak_lanjut,
                          peserta_list, pimpinan, notulis, kepala, dokumentasi_files, output_path: Path,
                          struktur: str = "lengkap", pendahuluan_text: str = None, pertanyaan_jawaban=None):
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)

    # Times New Roman 12pt & judul hitam tegas - meniru Template_Notula_Rapat.docx
    # resmi BPS, menggantikan tampilan Calibri default yang terkesan seperti
    # dokumen buatan AI generik.
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    heading1 = doc.styles["Heading 1"]
    heading1.font.name = "Times New Roman"
    heading1.font.size = Pt(14)
    heading1.font.bold = True
    heading1.font.color.rgb = RGBColor(0, 0, 0)

    heading2 = doc.styles["Heading 2"]
    heading2.font.name = "Times New Roman"
    heading2.font.size = Pt(12)
    heading2.font.bold = True
    heading2.font.color.rgb = RGBColor(0, 0, 0)

    _add_letterhead(doc)

    title = doc.add_heading(f"NOTULA KEGIATAN {meeting.judul_rapat.upper()}", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    _info_table(doc, meeting)
    _peserta_table(doc, peserta_list)
    doc.add_paragraph("")
    _pendahuluan_paragraph(doc, meeting, pimpinan, pendahuluan_text)
    if struktur == "ringkas":
        _pembahasan_ringkas_section(doc, ringkasan)
        _tanya_jawab_section(doc, pertanyaan_jawaban or [])
    else:
        _pembahasan_section(doc, ringkasan, keputusan)
        _tindak_lanjut_table(doc, tindak_lanjut)
    _tanda_tangan(doc, meeting, kepala, notulis)
    _dokumentasi_section(doc, meeting, dokumentasi_files)

    if transcript_text:
        doc.add_page_break()
        doc.add_heading("Lampiran: Transkripsi Rekaman Rapat", level=2)
        doc.add_paragraph(transcript_text)

    doc.save(output_path)
    _fix_zoom_schema_quirk(output_path)
    return output_path


# ============================================================
#  EKSPOR BERBASIS TEMPLATE WORD ASLI (NOTULA_TEMPLATE_PATH)
# ============================================================
def _replace_run_text(paragraph, mapping: dict):
    """Ganti {{token}} di seluruh run sebuah paragraf sekaligus (bukan
    per-run), karena Word sering memecah satu kalimat visual jadi beberapa
    <w:r> (mis. akibat pemeriksaan ejaan) - replace per-run naif bisa gagal
    kalau token terpecah di tengah. Format run pertama dipertahankan, run
    sisanya dikosongkan (penyederhanaan yang wajar untuk sekadar isi teks)."""
    full = "".join(r.text for r in paragraph.runs)
    if not full or "{{" not in full:
        return
    for key, val in mapping.items():
        full = full.replace(key, str(val))
    if paragraph.runs:
        paragraph.runs[0].text = full
        for r in paragraph.runs[1:]:
            r.text = ""
    else:
        paragraph.add_run(full)


def _replace_in_cell(cell, mapping: dict):
    for p in cell.paragraphs:
        _replace_run_text(p, mapping)
    # Blok tanda tangan (Kepala/Notulis) ada di tabel BERSARANG di dalam sel
    # gabungan Pendahuluan/Pembahasan (lihat build_notula_from_template) -
    # doc.tables python-docx hanya memuat tabel level atas, jadi perlu turun
    # rekursif ke cell.tables supaya placeholder di dalamnya ikut terganti.
    for nested in cell.tables:
        for row in nested.rows:
            for nested_cell in row.cells:
                _replace_in_cell(nested_cell, mapping)


def _replace_simple_placeholders(doc: Document, mapping: dict):
    for p in doc.paragraphs:
        _replace_run_text(p, mapping)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                _replace_in_cell(cell, mapping)


def _set_cell_plain_text(cell, text: str):
    # Pertahankan formatting run pertama (font Times New Roman template
    # tersimpan langsung di tiap <w:r>, bukan lewat style "Normal" - lihat
    # docDefaults template yang sebenarnya Calibri) - kalau sel benar-benar
    # tanpa run sama sekali, set TNR eksplisit sebagai jaring pengaman.
    p = cell.paragraphs[0]
    if p.runs:
        p.runs[0].text = text
        for r in list(p.runs[1:]):
            r._element.getparent().remove(r._element)
    else:
        run = p.add_run(text)
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
    for extra in list(cell.paragraphs[1:]):
        extra._element.getparent().remove(extra._element)


def _fill_peserta_rows(table, peserta_list):
    """Baris ke-3 tabel peserta (index 2, kosong di template) dipakai sebagai
    pola yang digandakan sesuai jumlah peserta sesungguhnya (2 orang/baris) -
    baris ke-4 (index 3, kosong juga di template asli) dibuang karena
    jumlahnya sekarang ditentukan dinamis, bukan tetap 2 baris."""
    row2, row3, row4 = table.rows[2], table.rows[3], table.rows[4]
    pattern = deepcopy(row2._tr)
    anchor = row4._tr

    pairs = []
    if peserta_list:
        for i in range(0, len(peserta_list), 2):
            pairs.append((peserta_list[i], peserta_list[i + 1] if i + 1 < len(peserta_list) else None))
    else:
        pairs = [(None, None)]

    row2._tr.getparent().remove(row2._tr)
    row3._tr.getparent().remove(row3._tr)

    import docx.table as _docx_table
    for left, right in pairs:
        new_tr = deepcopy(pattern)
        anchor.addprevious(new_tr)
        new_row = _docx_table._Row(new_tr, table)
        cells = new_row.cells
        _set_cell_plain_text(cells[0], (left.nama if left else "") or "")
        _set_cell_plain_text(cells[1], (left.jabatan if left else "") or "")
        _set_cell_plain_text(cells[2], (right.nama if right else "") or "")
        _set_cell_plain_text(cells[3], (right.jabatan if right else "") or "")


def _find_paragraph(container, token: str):
    for p in container.paragraphs:
        if p.text.strip() == token:
            return p
    return None


def _expand_pembahasan(cell, ringkasan, keputusan, tindak_lanjut, pertanyaan_jawaban, struktur,
                        gambar_pembahasan=None):
    target = _find_paragraph(cell, "{{pembahasan}}")
    if target is None:
        return
    anchor = target._p
    gambar_by_index = {g["index"]: g["paths"] for g in (gambar_pembahasan or []) if g.get("paths")}

    def insert_after(text, bold=False):
        nonlocal anchor
        new_p_el = anchor.makeelement(qn("w:p"), {})
        anchor.addnext(new_p_el)
        from docx.text.paragraph import Paragraph
        new_p = Paragraph(new_p_el, target._parent)
        r = new_p.add_run(text)
        r.bold = bold
        # Paragraf ini XML mentah baru (tanpa pPr/rPr) - font TNR template
        # cuma tersimpan sebagai direct-formatting per-run di teks asli,
        # bukan lewat style "Normal" (docDefaults template = Calibri), jadi
        # kalau tidak di-set eksplisit di sini hasilnya jadi Calibri.
        r.font.name = "Times New Roman"
        r.font.size = Pt(12)
        anchor = new_p_el
        return new_p

    def insert_images_after(paths):
        # Ukuran dimaksimalkan supaya tetap muat 1 halaman (item #61) - 1
        # gambar diberi tinggi lebih besar, 2 gambar masing-masing dikecilkan
        # supaya keduanya + teks sekitarnya tidak meluber ke halaman berikut.
        nonlocal anchor
        height_cm = 16 if len(paths) == 1 else 9
        for filename in paths[:2]:
            full_path = settings.DOKUMEN_DIR / filename
            new_p_el = anchor.makeelement(qn("w:p"), {})
            anchor.addnext(new_p_el)
            from docx.text.paragraph import Paragraph
            new_p = Paragraph(new_p_el, target._parent)
            new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = new_p.add_run()
            try:
                run.add_picture(str(full_path), height=Cm(height_cm))
            except Exception:
                run.text = "[Gagal memuat gambar]"
            anchor = new_p_el

    if struktur == "ringkas":
        if ringkasan:
            for i, point in enumerate(ringkasan, start=1):
                insert_after(f"{i}. {point}")
                if (i - 1) in gambar_by_index:
                    insert_images_after(gambar_by_index[i - 1])
        else:
            insert_after("Tidak ada poin pembahasan yang tercatat.")
        insert_after("")
        insert_after("Pertanyaan dan Jawaban", bold=True)
        if pertanyaan_jawaban:
            for item in pertanyaan_jawaban:
                insert_after(f"T: {item.get('pertanyaan', '')}", bold=True)
                insert_after(f"J: {item.get('jawaban', '')}")
        else:
            insert_after("Tidak ada tanya jawab yang tercatat.")
    else:
        if ringkasan:
            for i, point in enumerate(ringkasan, start=1):
                insert_after(f"{i}. {point}")
        else:
            insert_after("Tidak ada poin pembahasan yang tercatat.")
        insert_after("")
        insert_after("Keputusan Rapat", bold=True)
        if keputusan:
            for point in keputusan:
                insert_after(f"- {point}")
        else:
            insert_after("Tidak ada keputusan yang tercatat.")
        insert_after("")
        insert_after("Tindak Lanjut", bold=True)
        if tindak_lanjut:
            for item in tindak_lanjut:
                pic = item.get("penanggung_jawab") or "-"
                deadline = item.get("deadline") or "-"
                insert_after(f"- {item['deskripsi']} (PJ: {pic}, Tenggat: {deadline})")
        else:
            insert_after("Tidak ada tindak lanjut yang teridentifikasi.")

    # Paragraf placeholder asli sekarang hanya sisa tanda "{{pembahasan}}" -
    # hapus, isinya sudah digantikan paragraf-paragraf di atas.
    target._p.getparent().remove(target._p)


def _fill_dokumentasi_template(doc: Document, dokumentasi_files):
    target = _find_paragraph(doc, "{{dokumentasi}}")
    if target is None:
        return
    if not dokumentasi_files:
        for r in list(target.runs):
            r._element.getparent().remove(r._element)
        run = target.add_run("Tidak ada bukti dokumentasi yang diunggah untuk kegiatan ini.")
        run.italic = True
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
        target.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return

    photos = list(dokumentasi_files)
    rows_needed = (len(photos) + 1) // 2
    table = doc.add_table(rows=rows_needed, cols=2)
    idx = 0
    for r in range(rows_needed):
        for c in range(2):
            if idx >= len(photos):
                break
            cell = table.rows[r].cells[c]
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            try:
                run.add_picture(str(photos[idx]["path"]), width=Cm(7))
            except Exception:
                para.add_run("[Gagal memuat gambar]")
            if photos[idx].get("keterangan"):
                cap = cell.add_paragraph(photos[idx]["keterangan"])
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if cap.runs:
                    cap.runs[0].italic = True
                    cap.runs[0].font.size = Pt(9)
                    cap.runs[0].font.name = "Times New Roman"
            idx += 1

    # Tabel baru otomatis ditambahkan python-docx di AKHIR dokumen - pindahkan
    # ke posisi placeholder "{{dokumentasi}}" lalu buang paragraf placeholder-nya.
    target._p.addnext(table._tbl)
    target._p.getparent().remove(target._p)


def _find_paragraph_in_cell(cell, token: str):
    for p in cell.paragraphs:
        if token in p.text:
            return p
    for nested in cell.tables:
        for row in nested.rows:
            for nested_cell in row.cells:
                found = _find_paragraph_in_cell(nested_cell, token)
                if found is not None:
                    return found
    return None


def _find_paragraph_anywhere(doc, token: str):
    for p in doc.paragraphs:
        if token in p.text:
            return p
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                found = _find_paragraph_in_cell(cell, token)
                if found is not None:
                    return found
    return None


def _insert_ttd_image(doc, token: str, image_path):
    """Sisipkan gambar tanda tangan digital (kalau ada) di paragraf baru TEPAT
    SEBELUM paragraf yang memuat token nama (mis. {{notulis_nama}}) - harus
    dipanggil SEBELUM _replace_simple_placeholders() supaya token masih ada
    untuk dicari (fungsi itu mengganti isi teksnya, bukan menghapus paragraf)."""
    if not image_path:
        return
    target = _find_paragraph_anywhere(doc, token)
    if target is None:
        return
    from docx.text.paragraph import Paragraph
    new_p_el = target._p.makeelement(qn("w:p"), {})
    target._p.addprevious(new_p_el)
    new_p = Paragraph(new_p_el, target._parent)
    new_p.alignment = target.alignment
    run = new_p.add_run()
    try:
        run.add_picture(str(image_path), height=Cm(1.5))
    except Exception:
        pass


def build_notula_from_template(meeting, ringkasan, keputusan, tindak_lanjut, peserta_list,
                                notulis, kepala, dokumentasi_files, output_path: Path,
                                struktur: str = "ringkas", pendahuluan_text: str = None,
                                pertanyaan_jawaban=None, notulis_ttd_path=None, pimpinan_ttd_path=None,
                                gambar_pembahasan=None):
    """Versi ekspor yang mengisi Template_Notula_Rapat.docx resmi BPS Kabupaten
    Sanggau langsung (lewat NOTULA_TEMPLATE_PATH, salinan berplaceholder dari
    file itu) alih-alih membangun dokumen dari nol seperti
    build_notulensi_docx() - hasil visualnya jadi identik dengan template Word
    asli (kop surat, font, gaya tabel bawaan file itu sendiri)."""
    if not NOTULA_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Template notula tidak ditemukan: {NOTULA_TEMPLATE_PATH}")
    doc = Document(str(NOTULA_TEMPLATE_PATH))

    judul_upper = (meeting.judul_rapat or "").upper()
    unit_kerja = meeting.unit_kerja or settings.UNIT_KERJA_DEFAULT
    # "Kota, tanggal" pada blok tanda tangan - kota diambil dari kata terakhir
    # nama unit kerja, sama seperti build_notulensi_docx()/_tanda_tangan().
    kota = unit_kerja.split(" ")[-1]
    # Sisipkan gambar ttd (kalau ada) SEBELUM penggantian placeholder teks -
    # {{kepala_nama}} dipakai sebagai slot "Mengetahui" (kiri, otoritas
    # persetujuan) untuk ttd Pimpinan Rapat; {{notulis_nama}} untuk ttd Notulis.
    _insert_ttd_image(doc, "{{kepala_nama}}", pimpinan_ttd_path)
    _insert_ttd_image(doc, "{{notulis_nama}}", notulis_ttd_path)
    _replace_simple_placeholders(doc, {
        "{{judul_rapat_upper}}": judul_upper,
        "{{unit_kerja_upper}}": unit_kerja.upper(),
        "{{unit_kerja}}": unit_kerja,
        "{{tanggal}}": format_tanggal_singkat(meeting.tanggal),
        "{{topik}}": meeting.judul_rapat or "-",
        "{{tempat}}": meeting.lokasi or "-",
        "{{pendahuluan}}": pendahuluan_text or "",
        "{{notulis_nama}}": notulis.nama if notulis else "-",
        "{{kepala_nama}}": kepala.nama if kepala else "-",
        "{{tempat_tanggal}}": f"{kota}, {format_tanggal_singkat(meeting.tanggal)}",
    })

    _fill_peserta_rows(doc.tables[1], peserta_list)
    _expand_pembahasan(doc.tables[1].rows[-1].cells[0], ringkasan, keputusan,
                        tindak_lanjut, pertanyaan_jawaban or [], struktur,
                        gambar_pembahasan=gambar_pembahasan)
    _fill_dokumentasi_template(doc, dokumentasi_files)

    doc.save(output_path)
    _fix_zoom_schema_quirk(output_path)
    return output_path


def _fix_zoom_schema_quirk(docx_path: Path):
    """python-docx's bundled default template omits w:percent on <w:zoom>,
    which is technically required by the OOXML schema (cosmetic issue only —
    Word/LibreOffice open the file fine either way, but this keeps the output
    fully schema-valid)."""
    import os
    import zipfile
    import shutil
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(tmp_fd)  # hanya perlu path-nya; fd yang tertinggal terbuka mengunci
                       # file di Windows dan membuat shutil.move() di bawah gagal
                       # dengan WinError 32
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/settings.xml" and b'w:zoom' in data and b'w:percent' not in data:
                data = data.replace(b'<w:zoom w:val="bestFit"/>', b'<w:zoom w:val="bestFit" w:percent="100"/>')
            zout.writestr(item, data)
    shutil.move(tmp_path, docx_path)
