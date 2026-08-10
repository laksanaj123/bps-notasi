"""Util pemformatan tanggal & waktu ala Bahasa Indonesia (tanpa bergantung locale OS)."""
from datetime import datetime, date

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_tanggal_lengkap(value: str) -> str:
    """'2026-05-04' -> 'Senin, 4 Mei 2026'"""
    d = parse_date(value)
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month]} {d.year}"


def format_tanggal_singkat(value: str) -> str:
    """'2026-05-04' -> '4 Mei 2026'"""
    d = parse_date(value)
    return f"{d.day} {BULAN[d.month]} {d.year}"


def format_jam(value: str) -> str:
    """'08:30' -> '08.30 WIB'  (menerima None/'' dengan aman)"""
    if not value:
        return "-"
    return value.replace(":", ".") + " WIB"


def hitung_durasi(mulai: str, selesai: str) -> str:
    """('08:30','10:00') -> '1,5 jam'. Mengembalikan '-' jika data tidak lengkap."""
    if not mulai or not selesai:
        return "-"
    try:
        t1 = datetime.strptime(mulai, "%H:%M")
        t2 = datetime.strptime(selesai, "%H:%M")
        delta_menit = (t2 - t1).total_seconds() / 60
        if delta_menit <= 0:
            return "-"
        jam = delta_menit / 60
        jam_rounded = round(jam * 2) / 2  # pembulatan ke 0,5 jam terdekat
        if jam_rounded == int(jam_rounded):
            return f"{int(jam_rounded)} jam"
        return f"{jam_rounded}".replace(".", ",") + " jam"
    except ValueError:
        return "-"
