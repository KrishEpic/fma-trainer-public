"""Local-only routes for reviewing the images used by the public trainer."""

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from app.image_overrides import (
    ImageOverrideError,
    image_slots,
    load_override_data,
    problem_review_state,
    revert_manual_image,
    save_manual_image,
    set_review_status,
)
from app.problem_store import ProblemDataError, find_problem, load_problems


management = Blueprint("management", __name__)


@management.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"error": "The uploaded image is too large."}), 413


@management.before_request
def protect_management_routes():
    """Require explicit management mode, localhost, and a same-app write header."""
    if not current_app.config.get("MANAGEMENT_MODE"):
        abort(404)
    if not current_app.testing and request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(403)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
        "X-Management-Request"
    ) != "1":
        abort(403)


@management.get("/manage")
def management_page():
    return render_template("manage.html")


@management.get("/api/manage/problems")
def list_managed_problems():
    try:
        problems = _generated_problems()
        overrides = _overrides()
    except (ProblemDataError, ImageOverrideError) as error:
        return jsonify({"error": str(error)}), 500

    summaries = []
    for problem in sorted(problems, key=_problem_sort_key):
        state = problem_review_state(overrides, problem["id"])
        quality_warnings = _quality_warnings(problem)
        summaries.append(
            {
                "id": problem["id"],
                "year": problem["year"],
                "exam_version": problem["exam_version"],
                "problem_number": problem["problem_number"],
                "suspicious": bool(quality_warnings),
                "quality_warnings": quality_warnings,
                **state,
            }
        )
    return jsonify({"problems": summaries, "total": len(summaries)})


@management.get("/api/manage/problems/<problem_id>")
def managed_problem(problem_id):
    try:
        generated_problem = find_problem(_generated_problems(), problem_id)
        resolved_problem = find_problem(_resolved_problems(), problem_id)
        overrides = _overrides()
    except (ProblemDataError, ImageOverrideError) as error:
        return jsonify({"error": str(error)}), 500
    if generated_problem is None or resolved_problem is None:
        return jsonify({"error": "That published problem was not found."}), 404

    return jsonify(
        {
            "problem": resolved_problem,
            "review": problem_review_state(overrides, problem_id),
            "quality_warnings": _quality_warnings(generated_problem),
            "image_slots": image_slots(
                generated_problem, resolved_problem, overrides
            ),
        }
    )


@management.post("/api/manage/problems/<problem_id>/status")
def update_image_status(problem_id):
    submission = request.get_json(silent=True)
    if not isinstance(submission, dict):
        return jsonify({"error": "Submit an image review status as JSON."}), 400
    if find_problem(_generated_problems(), problem_id) is None:
        return jsonify({"error": "That published problem was not found."}), 404
    try:
        state = set_review_status(
            current_app.config["IMAGE_OVERRIDES_FILE"],
            current_app.config["IMAGE_OVERRIDE_STATIC_ROOT"],
            problem_id,
            submission.get("status"),
        )
    except ImageOverrideError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"review": state})


@management.post("/api/manage/problems/<problem_id>/images/<path:slot>/upload")
def upload_problem_image(problem_id, slot):
    problem = find_problem(_generated_problems(), problem_id)
    if problem is None:
        return jsonify({"error": "That published problem was not found."}), 404
    try:
        save_manual_image(
            override_file=current_app.config["IMAGE_OVERRIDES_FILE"],
            static_root=current_app.config["IMAGE_OVERRIDE_STATIC_ROOT"],
            manual_image_dir=current_app.config["MANUAL_IMAGE_DIR"],
            problem=problem,
            slot=slot,
            uploaded_file=request.files.get("image"),
            max_bytes=current_app.config["MANUAL_IMAGE_MAX_BYTES"],
        )
    except ImageOverrideError as error:
        return jsonify({"error": str(error)}), 400
    return managed_problem(problem_id)


@management.delete("/api/manage/problems/<problem_id>/images/<path:slot>")
def revert_problem_image(problem_id, slot):
    if find_problem(_generated_problems(), problem_id) is None:
        return jsonify({"error": "That published problem was not found."}), 404
    try:
        revert_manual_image(
            current_app.config["IMAGE_OVERRIDES_FILE"],
            current_app.config["IMAGE_OVERRIDE_STATIC_ROOT"],
            problem_id,
            slot,
        )
    except ImageOverrideError as error:
        return jsonify({"error": str(error)}), 400
    return managed_problem(problem_id)


def _generated_problems():
    return load_problems(current_app.config["PROBLEMS_FILE"])


def _resolved_problems():
    return load_problems(
        current_app.config["PROBLEMS_FILE"],
        current_app.config["IMAGE_OVERRIDES_FILE"],
        current_app.config["IMAGE_OVERRIDE_STATIC_ROOT"],
    )


def _overrides():
    return load_override_data(
        current_app.config["IMAGE_OVERRIDES_FILE"],
        current_app.config["IMAGE_OVERRIDE_STATIC_ROOT"],
    )


def _problem_sort_key(problem):
    return (
        problem["year"],
        problem["exam_version"] or "",
        problem["problem_number"],
    )


def _quality_warnings(problem):
    images = list(problem.get("question_images", []))
    images.extend(
        choice["image"]
        for choice in problem.get("choices", [])
        if choice.get("image") is not None
    )
    warnings = []
    for image in images:
        warnings.extend(image.get("quality", {}).get("warnings", []))
    return list(dict.fromkeys(warnings))
