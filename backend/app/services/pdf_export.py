"""
Konversi dokumen .docx menjadi .pdf menggunakan LibreOffice (gratis, lintas OS).

LibreOffice dipilih karena menghasilkan PDF yang tampilannya identik dengan
dokumen Word-nya (termasuk kop, tabel, dan gambar dokumentasi), tanpa perlu
menulis ulang seluruh logika template untuk mesin PDF terpisah.

Jika LibreOffice belum terpasang, fungsi melempar error dengan petunjuk
instalasi yang jelas (frontend menampilkannya apa adanya).
"""
import shutil
import subprocess
from pathlib import Path

# Kandidat lokasi executable LibreOffice di berbagai OS
_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def find_soffice() -> str | None:
    for cand in _CANDIDATES:
        found = shutil.which(cand)
        if found:
            return found
        if Path(cand).exists():
            return cand
    return None


def convert_docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    exe = find_soffice()
    if not exe:
        raise RuntimeError(
            "LibreOffice tidak ditemukan di server. Fitur Export PDF membutuhkan "
            "LibreOffice (gratis): unduh dari https://www.libreoffice.org lalu "
            "instal, kemudian jalankan ulang server NOTASI. "
            "(Export Word tetap bisa digunakan tanpa LibreOffice.)"
        )
    result = subprocess.run(
        [exe, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        capture_output=True, timeout=180,
    )
    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if result.returncode != 0 or not pdf_path.exists():
        stderr = (result.stderr or b"").decode(errors="ignore")[:300]
        raise RuntimeError(f"Konversi PDF oleh LibreOffice gagal. Detail: {stderr or 'tidak ada pesan'}")
    return pdf_path
