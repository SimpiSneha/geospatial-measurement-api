import shutil
import zipfile
from pathlib import Path

from fastapi import UploadFile

UPLOAD_DIR = Path("uploads")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024       # 50 MB per upload
MAX_UNZIPPED_BYTES = 200 * 1024 * 1024    # guards against zip bombs
ALLOWED_EXTENSIONS = {".kml", ".zip"}


class InvalidUpload(Exception):
    """The upload was rejected. The message is safe to show to the client."""


class FileTooLarge(InvalidUpload):
    pass


def file_dir(file_id: str) -> Path:
    return UPLOAD_DIR / file_id


def _shp_files(root: Path) -> list[Path]:
    """Find .shp files, skipping the junk macOS adds to zips."""
    return sorted(
        p for p in root.rglob("*.shp")
        if "__MACOSX" not in p.parts and not p.name.startswith("._")
    )


def _extract_zip_safely(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.infolist()
            if sum(m.file_size for m in members) > MAX_UNZIPPED_BYTES:
                raise InvalidUpload("Zip contents are too large.")
            for m in members:
                # Zip slip check: every file must land inside the target folder.
                if not (root / m.filename).resolve().is_relative_to(root):
                    raise InvalidUpload("Zip contains an unsafe file path.")
            zf.extractall(root)
    except zipfile.BadZipFile:
        raise InvalidUpload("The file is not a valid zip archive.") from None

    if not _shp_files(root):
        raise InvalidUpload("The zip does not contain a .shp file.")


def save_upload(upload: UploadFile, file_id: str) -> None:
    """Validate and store an upload under uploads/<file_id>/. Cleans up if it fails."""
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidUpload("Only .kml or .zip (containing a shapefile) files are supported.")

    target_dir = file_dir(file_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    saved = target_dir / f"upload{ext}"   # our own name, never the client's

    try:
        size = 0
        with open(saved, "wb") as out:
            while chunk := upload.file.read(1024 * 1024):   # read 1 MB at a time
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise FileTooLarge("File exceeds the 50 MB upload limit.")
                out.write(chunk)

        if size == 0:
            raise InvalidUpload("The uploaded file is empty.")

        if ext == ".zip":
            _extract_zip_safely(saved, target_dir / "extracted")
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)   # leave no half-saved files
        raise


def find_source_file(file_id: str) -> Path:
    """Locate the main geospatial file for an upload (used in Step 5)."""
    d = file_dir(file_id)
    kml = d / "upload.kml"
    if kml.exists():
        return kml
    shp = _shp_files(d / "extracted")
    if shp:
        return shp[0]
    raise FileNotFoundError(f"No geospatial file found for {file_id}")