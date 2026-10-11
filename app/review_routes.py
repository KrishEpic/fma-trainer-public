"""Local-only page and API routes for reviewing imported problems."""

from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

from app.review_store import (
    ReviewDataError,
    VerifiedProblemError,
    load_review_dataset,
    mark_problem_verified,
    prepare_problem_for_review,
    sorted_review_problems,
    update_problem,
)


review = Blueprint("review", __name__)


@review.before_request
def require_local_request():
    """Keep the file-editing tool available only from this computer."""
    if not current_app.testing and request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(403)


@review.get("/review")
def review_page():
    """Show the generated-problem review interface."""
    return render_template("review.html")


@review.get("/api/review/problems")
def list_review_problems():
    """Return all draft problems, with unresolved records first."""
    try:
        dataset = load_review_dataset(current_app.config["GENERATED_PROBLEMS_FILE"])
    except ReviewDataError as error:
        return jsonify({"error": str(error)}), 500

    problems = [
        prepare_problem_for_review(problem)
        for problem in sorted_review_problems(dataset)
    ]
    return jsonify(
        {
            "problems": problems,
            "counts": {
                "total": len(problems),
                "needs_review": sum(
                    problem.get("review_status") != "verified" for problem in problems
                ),
                "verified": sum(
                    problem.get("review_status") == "verified" for problem in problems
                ),
            },
        }
    )


@review.patch("/api/review/problems/<problem_id>")
def save_review_problem(problem_id):
    """Save the fields a reviewer is allowed to edit."""
    submission = request.get_json(silent=True)
    if not isinstance(submission, dict):
        return jsonify({"error": "Submit review changes as JSON."}), 400

    try:
        problem = update_problem(
            current_app.config["GENERATED_PROBLEMS_FILE"],
            problem_id,
            submission,
            allow_verified_edit=submission.get("allow_verified_edit") is True,
        )
    except VerifiedProblemError as error:
        return jsonify({"error": str(error)}), 409
    except ReviewDataError as error:
        status = 404 if "not found" in str(error) else 400
        return jsonify({"error": str(error)}), status
    return jsonify({"problem": problem})


@review.post("/api/review/problems/<problem_id>/verify")
def verify_review_problem(problem_id):
    """Lock a reviewed problem as verified."""
    try:
        problem = mark_problem_verified(
            current_app.config["GENERATED_PROBLEMS_FILE"], problem_id
        )
    except ReviewDataError as error:
        status = 404 if "not found" in str(error) else 400
        return jsonify({"error": str(error)}), status
    return jsonify({"problem": problem})


@review.get("/review/source/<path:filename>")
def source_pdf(filename):
    """Open an original source PDF after checking it belongs to the dataset."""
    if Path(filename).name != filename:
        abort(404)

    try:
        dataset = load_review_dataset(current_app.config["GENERATED_PROBLEMS_FILE"])
    except ReviewDataError:
        abort(404)

    allowed_files = {
        document.get("filename")
        for document in dataset.get("source_documents", [])
        if isinstance(document, dict)
    }
    if filename not in allowed_files:
        abort(404)

    return send_from_directory(current_app.config["SOURCE_PDF_DIR"], filename)
