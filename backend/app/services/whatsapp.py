"""
Kirim pesan WhatsApp otomatis lewat WhatsApp Cloud API (Meta) - resmi &
gratis untuk volume notifikasi internal seperti ini (lihat batas gratis di
developers.facebook.com/docs/whatsapp/pricing). Ini BUKAN whatsapp-web.js/
Baileys/pywhatkit (otomatisasi tidak resmi yang melanggar Ketentuan Layanan
WhatsApp dan berisiko nomor diblokir) - Cloud API adalah jalur resmi Meta.

Batasan penting yang WAJIB dipahami sebelum memakai modul ini (bukan bug,
memang aturan platform WhatsApp Business):
  1. Tidak bisa kirim teks bebas ke nomor yang belum pernah membalas chat
     bisnis ini dalam 24 jam terakhir - HARUS lewat "message template" yang
     sudah dibuat & disetujui Meta (WhatsApp Manager > Message Templates).
     Karena itu kirim_pesan_template() di bawah, bukan kirim teks polos.
  2. Mode uji coba (belum verifikasi bisnis) cuma bisa kirim ke maksimal 5
     nomor yang didaftarkan manual sebagai "nomor penerima uji" di WhatsApp
     Manager. Nomor pegawai sungguhan baru bisa dikirimi setelah verifikasi
     bisnis (tetap gratis, tapi proses administratif terpisah di Meta).
  3. Kredensial (WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID) didapat
     gratis dari developers.facebook.com - lihat README bagian "Kirim
     WhatsApp Otomatis" untuk langkah lengkapnya.

Kosong/gagal di sini TIDAK boleh menggagalkan alur utama (rapat/notula tetap
tersimpan normal) - pemanggil selalu menerima dict {ok, error} per nomor,
tidak pernah exception mentah.
"""
import requests

from ..config import settings


class WhatsAppError(Exception):
    pass


def _base_url() -> str:
    return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"


def _nomor_e164(nomor: str) -> str:
    """Normalisasi nomor ke format internasional tanpa '+' (format yang
    diminta WhatsApp Cloud API) - "0812xxx" -> "62812xxx"."""
    bersih = "".join(ch for ch in (nomor or "") if ch.isdigit() or ch == "+")
    bersih = bersih.lstrip("+")
    if bersih.startswith("0"):
        bersih = "62" + bersih[1:]
    return bersih


def kirim_pesan_template(nomor: str, template_name: str, parameters: list[str]) -> dict:
    """Kirim satu pesan template ke satu nomor. parameters diisi berurutan
    sesuai variabel {{1}}, {{2}}, dst di body template (lihat README untuk
    isi template notasi_undangan/notasi_notula yang dipakai kode ini).
    Return {"ok": True} atau {"ok": False, "error": "..."} - tidak pernah
    melempar exception ke pemanggil (lihat docstring modul)."""
    if not settings.WHATSAPP_READY:
        return {"ok": False, "error": "WhatsApp Cloud API belum dikonfigurasi (WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID kosong di .env)."}
    nomor_bersih = _nomor_e164(nomor)
    if not nomor_bersih:
        return {"ok": False, "error": "Nomor WhatsApp kosong/tidak valid."}
    payload = {
        "messaging_product": "whatsapp",
        "to": nomor_bersih,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANG},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in parameters],
            }],
        },
    }
    try:
        resp = requests.post(
            _base_url(),
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json=payload, timeout=20,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"Gagal terhubung ke WhatsApp Cloud API: {e}"}

    if resp.status_code == 200:
        return {"ok": True}
    # Meta mengembalikan detail error yang cukup jelas (mis. nomor belum
    # terverifikasi di mode uji coba, template belum disetujui, dst) -
    # diteruskan apa adanya supaya mudah didiagnosis dari UI.
    try:
        detail = resp.json().get("error", {}).get("message", resp.text[:200])
    except Exception:
        detail = resp.text[:200]
    return {"ok": False, "error": detail}


def kirim_teks_whacenter(nomor: str, pesan: str) -> dict:
    """Kirim SATU pesan teks polos ke satu nomor lewat gateway whacenter
    (lihat catatan panjang di config.py: TIDAK RESMI, hanya untuk percobaan).
    Berbeda dari kirim_pesan_template() di atas, di sini teks bebas boleh -
    itulah gunanya memakai gateway berbasis HP. Selalu return {"ok": ...} /
    {"ok": False, "error": "..."}, tidak pernah melempar exception ke pemanggil
    (sama seperti fungsi lain di modul ini)."""
    if not settings.WHACENTER_READY:
        return {"ok": False, "error": "whacenter belum dikonfigurasi (WHACENTER_DEVICE_ID kosong di .env)."}
    nomor_bersih = _nomor_e164(nomor)
    if not nomor_bersih:
        return {"ok": False, "error": "Nomor WhatsApp kosong/tidak valid."}
    try:
        resp = requests.post(settings.WHACENTER_API_URL, json={
            "device_id": settings.WHACENTER_DEVICE_ID,
            "number": nomor_bersih,
            "message": pesan,
        }, timeout=25)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Gagal terhubung ke whacenter: {e}"}

    try:
        body = resp.json()
    except Exception:
        body = {}
    status = body.get("status")
    if resp.status_code == 200 and status in (True, "true", 1, "success", "sent"):
        return {"ok": True}
    return {"ok": False, "error": str(body.get("message") or body.get("reason") or resp.text[:200])}
