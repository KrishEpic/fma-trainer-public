"""Web page and API routes for the trainer."""

import random

from flask import Blueprint, current_app, jsonify, render_template, request

from app.problem_store import (
    CHOICE_LABELS,
    ProblemDataError,
    find_problem,
    load_problems,
)


main = Blueprint("main", __name__)


@main.get("/")
def index():
    """Show the single-page practice interface."""
    return render_template("index.html")


@main.get("/api/problems/random")
def random_problem():
    """Return one random problem without revealing its answer."""
    try:
        problems = _get_problems()
    except ProblemDataError as error:
        return jsonify({"error": str(error)}), 500

    exam_key = request.args.get("exam")
    if exam_key:
        problems = [
            problem for problem in problems if _exam_key(problem) == exam_key
        ]
        if not problems:
            return jsonify({"error": "That exam was not found."}), 400

    problem = random.choice(problems)

    return jsonify(_public_problem(problem))


@main.get("/api/problems/catalog")
def problem_catalog():
    """Return answer-free metadata used for local practice selection."""
    try:
        problems = _get_problems()
    except ProblemDataError as error:
        return jsonify({"error": str(error)}), 500

    return jsonify(
        [
            {
                "id": problem["id"],
                "year": problem["year"],
                "exam_version": problem["exam_version"],
                "problem_number": problem["problem_number"],
                "exam_key": _exam_key(problem),
            }
            for problem in problems
        ]
    )


@main.get("/api/problems/<problem_id>")
def problem_by_id(problem_id):
    """Return one requested problem without revealing its answer."""
    try:
        problem = find_problem(_get_problems(), problem_id)
    except ProblemDataError as error:
        return jsonify({"error": str(error)}), 500

    if problem is None:
        return jsonify({"error": "That problem was not found."}), 404

    return jsonify(_public_problem(problem))


@main.get("/api/exams")
def exams():
    """List the exams available to the public trainer."""
    try:
        problems = _get_problems()
    except ProblemDataError as error:
        return jsonify({"error": str(error)}), 500

    available_exams = {}
    for problem in problems:
        key = _exam_key(problem)
        available_exams[key] = {
            "key": key,
            "year": problem["year"],
            "exam_version": problem["exam_version"],
            "label": _exam_label(problem),
        }

    return jsonify(
        sorted(
            available_exams.values(),
            key=lambda exam: (exam["year"], exam["exam_version"] or ""),
            reverse=True,
        )
    )


@main.post("/api/answers")
def check_answer():
    """Check a submitted answer and then reveal the correct one."""
    submission = request.get_json(silent=True)
    if not isinstance(submission, dict):
        return jsonify({"error": "Submit an answer as JSON."}), 400

    problem_id = submission.get("problem_id")
    answer = submission.get("answer")
    if (
        not isinstance(problem_id, str)
        or not isinstance(answer, str)
        or answer not in CHOICE_LABELS
    ):
        return jsonify({"error": "Choose an answer from A through E."}), 400

    try:
        problem = find_problem(_get_problems(), problem_id)
    except ProblemDataError as error:
        return jsonify({"error": str(error)}), 500

    if problem is None:
        return jsonify({"error": "That problem was not found."}), 404

    correct_answers = problem["correct_answers"]
    displayed_answer = " or ".join(correct_answers)
    return jsonify(
        {
            "correct": answer in correct_answers,
            # Keep the original field for existing API users.
            "correct_answer": displayed_answer,
            "correct_answers": correct_answers,
        }
    )


def _get_problems():
    """Load problems using the file configured for this application."""
    return load_problems(
        current_app.config["PROBLEMS_FILE"],
        current_app.config.get("IMAGE_OVERRIDES_FILE"),
        current_app.config.get("IMAGE_OVERRIDE_STATIC_ROOT"),
    )


def _public_problem(problem):
    """Build the problem representation that is safe before grading."""
    return {
        "id": problem["id"],
        "year": problem["year"],
        "exam_version": problem["exam_version"],
        "problem_number": problem["problem_number"],
        "question": problem["question"],
        "question_images": problem["question_images"],
        "choices": problem["choices"],
        "diagrams": problem["diagrams"],
    }


def _exam_key(problem):
    """Return the stable value used by the exam filter."""
    version = problem["exam_version"]
    return f"{problem['year']}-{version.lower()}" if version else str(problem["year"])


def _exam_label(problem):
    """Return a short label suitable for the filter menu."""
    version = problem["exam_version"]
    return f"{problem['year']} Exam {version}" if version else f"{problem['year']} F=ma"
