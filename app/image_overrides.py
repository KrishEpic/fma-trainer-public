"""Store durable manual image corrections separately from generated data."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from threading import Lock

from PIL import Image, UnidentifiedImageError


REVIEW_STATUSES = {
    "not_reviewed",
    "looks_good",
    "bad_crop",
    "manually_replaced",
}
ALLOWED_IMAGE_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}


class ImageOverrideError(Exception):
    """Raised when override data or an uploaded image is unsafe or malformed."""


_write_lock = Lock()


def empty_override_data():
    return {"schema_version": 1, "problems": {}}


def load_override_data(file_path, static_root):
    """Load and validate the manual override file, or return an empty store."""
    path = Path(file_path)
    if not path.exists():
        return empty_override_data()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImageOverrideError("The image override file could not be read.") from error

    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ImageOverrideError("The image override file must use schema version 1.")
    if not isinstance(data.get("problems"), dict):
        raise ImageOverrideError("The image override file needs a problems object.")

    for problem_id, record in data["problems"].items():
        _validate_override_record(problem_id, record, static_root)
    return data


def apply_overrides(problems, override_data):
    """Return problem copies whose active manual image paths take precedence."""
    overrides_by_id = override_data.get("problems", {})
    resolved = []
    for original_problem in problems:
        problem = deepcopy(original_problem)
        record = overrides_by_id.get(problem["id"], {})
        for slot, override in record.get("images", {}).items():
            image = _image_for_slot(problem, slot)
            if image is not None:
                image["path"] = override["path"]
                # Metrics describe the generated crop, not a later manual file.
                image.pop("quality", None)
        resolved.append(problem)
    return resolved


def problem_review_state(override_data, problem_id):
    record = override_data.get("problems", {}).get(problem_id, {})
    images = record.get("images", {})
    return {
        "status": record.get("status", "not_reviewed"),
        "has_manual_override": bool(images),
        "manual_slots": sorted(images),
    }


def set_review_status(file_path, static_root, problem_id, status):
    if status not in REVIEW_STATUSES:
        raise ImageOverrideError("Choose a valid image review status.")

    with _write_lock:
        data = load_override_data(file_path, static_root)
        record = data["problems"].setdefault(problem_id, {"images": {}})
        record["status"] = status
        record["updated_at"] = _utc_now()
        _save_override_data(file_path, data)
    return problem_review_state(data, problem_id)


def save_manual_image(
    *,
    override_file,
    static_root,
    manual_image_dir,
    problem,
    slot,
    uploaded_file,
    max_bytes,
):
    """Validate an upload, save it atomically, and activate its override."""
    generated_image = _image_for_slot(problem, slot)
    if generated_image is None:
        raise ImageOverrideError("That image slot does not exist for this problem.")
    if uploaded_file is None:
        raise ImageOverrideError("Choose an image to upload.")

    image_bytes = uploaded_file.stream.read(max_bytes + 1)
    if not image_bytes:
        raise ImageOverrideError("The uploaded image is empty.")
    if len(image_bytes) > max_bytes:
        raise ImageOverrideError(
            f"The uploaded image exceeds the {max_bytes // (1024 * 1024)} MB limit."
        )
    extension = _verified_image_extension(image_bytes)

    safe_slot = slot.replace(":", "-").lower()
    digest = sha256(image_bytes).hexdigest()[:20]
    destination_dir = Path(manual_image_dir) / problem["id"]
    destination = destination_dir / f"{safe_slot}-{digest}{extension}"

    static_root = Path(static_root).resolve()
    try:
        public_path = destination.resolve().relative_to(static_root).as_posix()
    except ValueError as error:
        raise ImageOverrideError("Manual images must stay inside the static directory.") from error
    _write_bytes_atomic(destination, image_bytes)

    with _write_lock:
        data = load_override_data(override_file, static_root)
        record = data["problems"].setdefault(problem["id"], {"images": {}})
        record.setdefault("images", {})[slot] = {
            "path": public_path,
            "uploaded_at": _utc_now(),
        }
        record["status"] = "manually_replaced"
        record["updated_at"] = _utc_now()
        _save_override_data(override_file, data)
    return problem_review_state(data, problem["id"])


def revert_manual_image(file_path, static_root, problem_id, slot):
    """Deactivate one override without deleting either generated or manual files."""
    with _write_lock:
        data = load_override_data(file_path, static_root)
        record = data["problems"].get(problem_id)
        if record is None or slot not in record.get("images", {}):
            raise ImageOverrideError("That image does not have a manual override.")

        del record["images"][slot]
        if not record["images"] and record.get("status") == "manually_replaced":
            record["status"] = "not_reviewed"
        record["updated_at"] = _utc_now()
        _save_override_data(file_path, data)
    return problem_review_state(data, problem_id)


def image_slots(generated_problem, resolved_problem, override_data):
    """Describe each generated/effective image for the management dashboard."""
    manual_slots = set(problem_review_state(override_data, generated_problem["id"])["manual_slots"])
    slots = []
    for index, (generated, effective) in enumerate(
        zip(generated_problem["question_images"], resolved_problem["question_images"]),
        start=1,
    ):
        key = f"question:{index}"
        slots.append(_slot_record(key, f"Question image {index}", generated, effective, manual_slots))
    for generated_choice, effective_choice in zip(
        generated_problem["choices"], resolved_problem["choices"]
    ):
        label = generated_choice["label"]
        key = f"choice:{label}"
        slots.append(
            _slot_record(
                key,
                f"Choice {label}",
                generated_choice["image"],
                effective_choice["image"],
                manual_slots,
            )
        )
    return slots


def _slot_record(key, label, generated, effective, manual_slots):
    return {
        "key": key,
        "label": label,
        "generated_image": generated,
        "effective_image": effective,
        "origin": "manual" if key in manual_slots else "auto",
    }


def _image_for_slot(problem, slot):
    if slot.startswith("question:"):
        try:
            index = int(slot.split(":", 1)[1]) - 1
        except ValueError:
            return None
        images = problem.get("question_images", [])
        return images[index] if 0 <= index < len(images) else None
    if slot.startswith("choice:"):
        label = slot.split(":", 1)[1]
        choice = next(
            (item for item in problem.get("choices", []) if item.get("label") == label),
            None,
        )
        return choice.get("image") if choice else None
    return None


def _validate_override_record(problem_id, record, static_root):
    if not isinstance(problem_id, str) or not problem_id:
        raise ImageOverrideError("Every override needs a problem ID.")
    if not isinstance(record, dict) or record.get("status", "not_reviewed") not in REVIEW_STATUSES:
        raise ImageOverrideError(f"Invalid review status for {problem_id}.")
    images = record.get("images", {})
    if not isinstance(images, dict):
        raise ImageOverrideError(f"Image overrides for {problem_id} must be an object.")
    for slot, image in images.items():
        if not isinstance(slot, str) or not isinstance(image, dict):
            raise ImageOverrideError(f"Invalid image override for {problem_id}.")
        path = image.get("path")
        if not isinstance(path, str):
            raise ImageOverrideError(f"Manual image path is missing for {problem_id}.")
        parts = PurePosixPath(path)
        if (
            parts.is_absolute()
            or ".." in parts.parts
            or parts.parts[:2] != ("problem_images", "manual")
        ):
            raise ImageOverrideError(f"Unsafe manual image path for {problem_id}.")
        if not (Path(static_root) / parts).is_file():
            raise ImageOverrideError(f"Manual image was not found: {path}")


def _verified_image_extension(image_bytes):
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            detected_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ImageOverrideError("The uploaded file is not a valid image.") from error
    extension = ALLOWED_IMAGE_FORMATS.get(detected_format)
    if extension is None:
        raise ImageOverrideError("Only PNG, JPEG, and WebP images are allowed.")
    return extension


def _write_bytes_atomic(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(contents)
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _save_override_data(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(data, temporary, indent=2, ensure_ascii=False)
            temporary.write("\n")
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()
