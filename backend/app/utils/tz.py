"""Waktu lokal WIB (GMT+7) - dipakai untuk semua stempel waktu yang
ditampilkan ke pengguna (dibuat_pada, waktu_mulai_aktual, dst).

WIB tidak punya perubahan musim (DST) dan offset-nya tetap +7 sejak 1988,
jadi timedelta tetap sudah cukup akurat tanpa perlu dependency tzdata/zoneinfo
tambahan. Hasilnya sengaja naive (tanpa tzinfo) supaya cocok dengan kolom
DateTime yang ada dan cara frontend mem-parse tanggal saat ini (sebagai
waktu lokal), tanpa perlu perubahan di frontend.

JANGAN dipakai untuk perhitungan masa berlaku token JWT (auth.py) - itu
tetap harus utcnow() murni, tidak berhubungan dengan tampilan ke pengguna.
"""
from datetime import datetime, timedelta


def now_wib() -> datetime:
    return datetime.utcnow() + timedelta(hours=7)
