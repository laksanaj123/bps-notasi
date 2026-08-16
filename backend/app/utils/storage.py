import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile


def _save_upload(file: UploadFile, dest_dir: Path, max_mb: int) -> Path:
    ext = Path(file.filename).suffix or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = dest_dir / fname
    max_bytes = max_mb * 1024 * 1024
    total = 0
    with open(dest, "wb") as buf:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                buf.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Ukuran berkas melebihi batas maksimum {max_mb} MB")
            buf.write(chunk)
    return dest
