"""Create and configure the Flask application."""

import os
from pathlib import Path

from flask import Flask


def create_app(test_config=None):
    """Build a Flask application with the settings it needs."""
    app = Flask(__name__)

    project_root = Path(app.root_path).parent
    app.config.from_mapping(
        PROBLEMS_FILE=project_root / "data" / "problems.json",
        GENERATED_PROBLEMS_FILE=project_root / "data" / "generated" / "demo-review.json",
        SOURCE_PDF_DIR=project_root / "source_pdfs",
        IMAGE_OVERRIDES_FILE=project_root / "data" / "problem_image_overrides.json",
        IMAGE_OVERRIDE_STATIC_ROOT=Path(app.static_folder),
        MANUAL_IMAGE_DIR=app.static_folder + "/problem_images/manual",
        MANUAL_IMAGE_MAX_BYTES=8 * 1024 * 1024,
        MAX_CONTENT_LENGTH=9 * 1024 * 1024,
        MANAGEMENT_MODE=os.environ.get("FMA_MANAGEMENT_MODE") == "1",
    )

    if test_config is not None:
        app.config.update(test_config)

    from app.routes import main

    app.register_blueprint(main)
    if app.config["MANAGEMENT_MODE"]:
        from app.management_routes import management
        from app.review_routes import review

        app.register_blueprint(management)
        app.register_blueprint(review)
    return app
