"""Read and validate version 2 problem records stored in JSON."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from app.image_overrides import ImageOverrideError, apply_overrides, load_override_data


CHOICE_LABELS = ("A", "B", "C", "D", "E")
STATIC_ROOT = Path(__file__).resolve().parent / "static"
REQUIRED_FIELDS = {
    "id",
    "year",
    "exam_version",
    "problem_number",
    "question",
    "question_images",
    "choices",
    "diagrams",
    "correct_answers",
    "source",
}


class ProblemDataError(Exception):
    """Raised when the problem file cannot be used safely."""


def load_problems(file_path, override_file=None, override_static_root=None):
    """Load a version 2 JSON file and return its validated problem records."""
    path = Path(file_path)

    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProblemDataError("The problem file could not be read.") from error

    if not isinstance(dataset, dict) or dataset.get("schema_version") != 2:
        raise ProblemDataError("The problem file must use schema version 2.")
    problems = dataset.get("problems")
    if not isinstance(problems, list) or not problems:
        raise ProblemDataError("The problem file must contain a non-empty problems list.")

    seen_ids = set()
    for problem in problems:
        _validate_problem(problem, seen_ids)

    if override_file is not None:
        try:
            override_data = load_override_data(
                override_file, override_static_root or STATIC_ROOT
            )
        except ImageOverrideError as error:
            raise ProblemDataError(str(error)) from error
        problems = apply_overrides(problems, override_data)

    return problems


def _validate_problem(problem, seen_ids):
    """Check one problem and raise a helpful error when it is malformed."""
    if not isinstance(problem, dict) or not REQUIRED_FIELDS.issubset(problem):
        raise ProblemDataError("Every problem must contain all required fields.")

    identifier = problem["id"]
    if not isinstance(identifier, str) or not identifier:
        raise ProblemDataError("Every problem must have a non-empty string ID.")
    if identifier in seen_ids:
        raise ProblemDataError("Problem IDs must be unique.")
    seen_ids.add(identifier)

    if (
        not isinstance(problem["year"], int)
        or problem["year"] <= 0
        or not isinstance(problem["problem_number"], int)
        or problem["problem_number"] <= 0
    ):
        raise ProblemDataError("Year and problem number must be positive integers.")

    exam_version = problem["exam_version"]
    if exam_version is not None and (
        not isinstance(exam_version, str) or not exam_version.strip()
    ):
        raise ProblemDataError("Exam version must be non-empty text or null.")
    if not isinstance(problem["question"], str) or not problem["question"].strip():
        raise ProblemDataError("Every problem must have non-empty question text.")

    question_images = problem["question_images"]
    if not isinstance(question_images, list) or not question_images:
        raise ProblemDataError("Every problem must have at least one question image.")
    for image in question_images:
        _validate_image(image)

    choices = problem["choices"]
    if not isinstance(choices, list) or len(choices) != len(CHOICE_LABELS):
        raise ProblemDataError("Each problem must have exactly five choices.")
    for expected_label, choice in zip(CHOICE_LABELS, choices):
        _validate_choice(choice, expected_label)

    diagrams = problem["diagrams"]
    if not isinstance(diagrams, list):
        raise ProblemDataError("Problem diagrams must be a list.")
    for diagram in diagrams:
        _validate_image(diagram)
        if diagram.get("placement") != "stem":
            raise ProblemDataError("Problem diagrams must use stem placement.")

    answers = problem["correct_answers"]
    if (
        not isinstance(answers, list)
        or not answers
        or len(answers) != len(set(answers))
        or any(answer not in CHOICE_LABELS for answer in answers)
    ):
        raise ProblemDataError("Correct answers must be unique labels from A through E.")

    _validate_source(problem["source"])


def _validate_choice(choice, expected_label):
    if not isinstance(choice, dict) or choice.get("label") != expected_label:
        raise ProblemDataError("Choices must be labeled A through E in order.")
    text = choice.get("text")
    image = choice.get("image")
    if text is not None and (not isinstance(text, str) or not text.strip()):
        raise ProblemDataError("Choice text must be non-empty text or null.")
    if image is not None:
        _validate_image(image)
    if image is None:
        raise ProblemDataError("Every published choice needs a source image.")


def _validate_image(image):
    if not isinstance(image, dict):
        raise ProblemDataError("Image information must be an object.")
    path = image.get("path")
    alt_text = image.get("alt_text")
    if not isinstance(path, str) or not path:
        raise ProblemDataError("Every image needs a path.")
    path_parts = PurePosixPath(path)
    if path_parts.is_absolute() or ".." in path_parts.parts:
        raise ProblemDataError("Image paths must stay inside the static directory.")
    if not path_parts.parts or path_parts.parts[0] != "problem_images":
        raise ProblemDataError("Problem images must be stored under problem_images/.")
    if not (STATIC_ROOT / path_parts).is_file():
        raise ProblemDataError(f"Problem image was not found: {path}")
    if not isinstance(alt_text, str) or not alt_text.strip():
        raise ProblemDataError("Every image needs non-empty alternative text.")
    quality = image.get("quality")
    if quality is not None:
        _validate_image_quality(quality)


def _validate_image_quality(quality):
    required_numbers = {
        "pixel_width",
        "pixel_height",
        "aspect_ratio",
        "whitespace_fraction",
        "source_pixel_width",
        "source_pixel_height",
        "trimmed_area_fraction",
    }
    if not isinstance(quality, dict):
        raise ProblemDataError("Image quality information must be an object.")
    if any(
        not isinstance(quality.get(field), (int, float))
        or isinstance(quality.get(field), bool)
        for field in required_numbers
    ):
        raise ProblemDataError("Image quality metrics must be numbers.")
    source_whitespace = quality.get("source_whitespace_fraction")
    if source_whitespace is not None and (
        not isinstance(source_whitespace, (int, float))
        or isinstance(source_whitespace, bool)
    ):
        raise ProblemDataError("Source whitespace must be a number when present.")
    warnings = quality.get("warnings")
    if not isinstance(warnings, list) or any(
        not isinstance(warning, str) or not warning for warning in warnings
    ):
        raise ProblemDataError("Image quality warnings must be a list of names.")


def _validate_source(source):
    if not isinstance(source, dict):
        raise ProblemDataError("Every imported problem needs source information.")
    for field in ("exam_pdf", "solutions_pdf"):
        if not isinstance(source.get(field), str) or not source[field]:
            raise ProblemDataError("Source PDF filenames must be non-empty text.")
    for field in ("exam_pages", "solutions_pages"):
        pages = source.get(field)
        if not isinstance(pages, list) or any(
            not isinstance(page, int) or page <= 0 for page in pages
        ):
            raise ProblemDataError("Source page lists must contain positive integers.")


def find_problem(problems, problem_id):
    """Return the problem with the requested ID, or None when it is absent."""
    return next((problem for problem in problems if problem["id"] == problem_id), None)
