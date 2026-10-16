from pathlib import Path
import re
from secrets import token_hex

from flask import current_app
from werkzeug.datastructures import FileStorage


MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


def save_image_upload(upload: FileStorage | None, category: str) -> str | None:
    if upload is None or not upload.filename:
        return None
    if category not in {"school", "students"}:
        raise ValueError("Unsupported image upload category.")

    extension = Path(upload.filename).suffix.lower()
    if extension not in IMAGE_SIGNATURES:
        raise ValueError("Upload a JPG, PNG, or WebP image.")

    contents = upload.stream.read(MAX_IMAGE_SIZE + 1)
    if len(contents) > MAX_IMAGE_SIZE:
        raise ValueError("Image files must be 5 MB or smaller.")

    valid_signature = any(
        contents.startswith(signature)
        for signature in IMAGE_SIGNATURES[extension]
    )
    if extension == ".webp":
        valid_signature = (
            contents.startswith(b"RIFF")
            and contents[8:12] == b"WEBP"
        )
    if not valid_signature:
        raise ValueError("The uploaded file does not match its image type.")

    filename = f"{token_hex(16)}{extension}"
    if category == "school":
        relative_path = Path("uploads") / category / filename
        destination = Path(current_app.static_folder) / relative_path
        stored_path = relative_path.as_posix()
    else:
        relative_path = Path(category) / filename
        destination = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]) / relative_path
        stored_path = relative_path.as_posix()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    return stored_path


def get_student_photo_path(photo_path: str) -> Path | None:
    match = re.fullmatch(
        r"students/([a-f0-9]{32}\.(?:jpg|jpeg|png|webp))",
        photo_path,
    )
    if match is None:
        return None
    path = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]) / "students" / match.group(1)
    return path if path.is_file() else None
