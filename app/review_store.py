"""Read and safely update draft problems during human review."""

import json
import os
import tempfile
from pathlib import Path
from threading import Lock


CHOICE_LABELS = ("A", "B", "C", "D", "E")
DIAGRAM_STATUSES = {
    "not_reviewed",
    "ok",
    "bad",
    "missing",
    "not_applicable",
}


class ReviewDataError(Exception):
    """Raised when generated problem data cannot be safely reviewed."""


class VerifiedProblemError(ReviewDataError):
    """Raised when a request tries to change a locked verified record."""


_write_lock = Lock()


def load_review_dataset(file_path):
    """Load the generated version 2 dataset and perform basic validation."""
    path = Path(file_path)
    try:
        with path.open(encoding="utf-8") as file:
            dataset = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewDataError(f"Could not read generated problems: {error}") from error

    if not isinstance(dataset, dict) or dataset.get("schema_version") != 2:
        raise ReviewDataError("The review tool requires a version 2 problem file.")
    if not isinstance(dataset.get("problems"), list):
        raise ReviewDataError("The generated problem file has no problems list.")

    return dataset


def sorted_review_problems(dataset):
    """Return problems needing review first, then order by exam and number."""
    return sorted(
        dataset["problems"],
        key=lambda problem: (
            problem.get("review_status") == "verified",
            problem.get("year", 0),
            problem.get("exam_version") or "",
            problem.get("problem_number", 0),
        ),
    )


def get_problem(dataset, problem_id):
    """Find one problem by its stable ID."""
    for problem in dataset["problems"]:
        if problem.get("id") == problem_id:
            return problem
    return None


def prepare_problem_for_review(problem):
    """Copy a problem and provide a default diagram-review status."""
    prepared = dict(problem)
    prepared["diagram_status"] = problem.get(
        "diagram_status", _default_diagram_status(problem)
    )
    return prepared


def update_problem(file_path, problem_id, changes, allow_verified_edit=False):
    """Apply the editable fields to one problem and save the whole dataset."""
    with _write_lock:
        dataset = load_review_dataset(file_path)
        problem = get_problem(dataset, problem_id)
        if problem is None:
            raise ReviewDataError("That generated problem was not found.")

        if problem.get("review_status") == "verified" and not allow_verified_edit:
            raise VerifiedProblemError(
                "This record is verified and locked. Explicitly unlock it before editing."
            )

        question = changes.get("question")
        choices = changes.get("choices")
        correct_answers = changes.get("correct_answers")
        diagram_status = changes.get(
            "diagram_status", problem.get("diagram_status", _default_diagram_status(problem))
        )

        _validate_question(question)
        normalized_choices = _validate_and_merge_choices(choices, problem["choices"])
        normalized_answers = _validate_answers(correct_answers)
        _validate_diagram_status(diagram_status)

        problem["question"] = question.strip()
        problem["choices"] = normalized_choices
        problem["correct_answers"] = normalized_answers
        problem["diagram_status"] = diagram_status

        # Editing a verified record means it needs another human check.
        if problem.get("review_status") == "verified" or diagram_status in {
            "bad",
            "missing",
        }:
            problem["review_status"] = "needs_review"

        _save_dataset(file_path, dataset)
        return prepare_problem_for_review(problem)


def mark_problem_verified(file_path, problem_id):
    """Mark a complete, visually reviewed problem as verified."""
    with _write_lock:
        dataset = load_review_dataset(file_path)
        problem = get_problem(dataset, problem_id)
        if problem is None:
            raise ReviewDataError("That generated problem was not found.")

        diagram_status = problem.get("diagram_status", _default_diagram_status(problem))
        _validate_question(problem.get("question"))
        _validate_and_merge_choices(problem.get("choices"), problem.get("choices"))
        _validate_answers(problem.get("correct_answers"))

        if _has_visual_assets(problem) and diagram_status != "ok":
            raise ReviewDataError(
                "Review the extracted diagrams/images and mark them OK before verifying."
            )
        if diagram_status in {"bad", "missing", "not_reviewed"}:
            raise ReviewDataError(
                "A problem with an unresolved image flag cannot be verified."
            )

        problem["diagram_status"] = diagram_status
        problem["review_status"] = "verified"
        _save_dataset(file_path, dataset)
        return prepare_problem_for_review(problem)


def _validate_question(question):
    if not isinstance(question, str) or not question.strip():
        raise ReviewDataError("Question text cannot be empty.")


def _validate_and_merge_choices(submitted_choices, stored_choices):
    if not isinstance(submitted_choices, list) or len(submitted_choices) != 5:
        raise ReviewDataError("A problem must have exactly five choices.")
    if not isinstance(stored_choices, list) or len(stored_choices) != 5:
        raise ReviewDataError("The stored choices are malformed.")

    merged = []
    for expected_label, submitted, stored in zip(
        CHOICE_LABELS, submitted_choices, stored_choices
    ):
        if not isinstance(submitted, dict) or submitted.get("label") != expected_label:
            raise ReviewDataError("Choices must be labeled A through E in order.")
        text = submitted.get("text")
        if text is not None and not isinstance(text, str):
            raise ReviewDataError(f"Choice {expected_label} text must be text or null.")
        text = text.strip() if isinstance(text, str) else None
        image = stored.get("image")
        if not text and image is None:
            raise ReviewDataError(
                f"Choice {expected_label} needs text or an existing choice image."
            )
        merged.append({"label": expected_label, "text": text or None, "image": image})
    return merged


def _validate_answers(answers):
    if not isinstance(answers, list) or not answers:
        raise ReviewDataError("Select at least one correct answer.")
    if any(answer not in CHOICE_LABELS for answer in answers):
        raise ReviewDataError("Correct answers must be labels A through E.")
    if len(set(answers)) != len(answers):
        raise ReviewDataError("Correct answers cannot contain duplicates.")
    return [label for label in CHOICE_LABELS if label in answers]


def _validate_diagram_status(status):
    if status not in DIAGRAM_STATUSES:
        raise ReviewDataError("Choose a valid diagram status.")


def _has_visual_assets(problem):
    if problem.get("diagrams"):
        return True
    return any(choice.get("image") for choice in problem.get("choices", []))


def _default_diagram_status(problem):
    return "not_reviewed" if _has_visual_assets(problem) else "not_applicable"


def _save_dataset(file_path, dataset):
    """Replace the JSON atomically so an interrupted write cannot corrupt it."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary_file:
            temporary_name = temporary_file.name
            json.dump(dataset, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
        os.replace(temporary_name, path)
    except OSError as error:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise ReviewDataError(f"Could not save review changes: {error}") from error
