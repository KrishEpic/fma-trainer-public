"""Tests for the public demonstration dataset and core trainer routes."""

import json
from pathlib import Path

import pytest
from PIL import Image

from app import create_app
from app.problem_store import load_problems


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBLEMS_FILE = PROJECT_ROOT / "data" / "problems.json"
STATIC_ROOT = PROJECT_ROOT / "app" / "static"


@pytest.fixture(scope="module")
def problems():
    return load_problems(PROBLEMS_FILE)


@pytest.fixture()
def client():
    application = create_app(
        {
            "TESTING": True,
            "MANAGEMENT_MODE": False,
            "PROBLEMS_FILE": PROBLEMS_FILE,
        }
    )
    return application.test_client()


def test_dataset_contains_only_original_demo_records(problems):
    raw = json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))

    assert raw["schema_version"] == 2
    assert raw["collection"]["kind"] == "original_public_demo"
    assert len(problems) == 8
    assert all(problem["id"].startswith("demo-") for problem in problems)
    assert {problem["exam_version"] for problem in problems} == {"Demo A", "Demo B"}
    assert all(
        problem["source"]["exam_pdf"] == "ORIGINAL-DEMO-CONTENT-NO-PDF"
        and problem["source"]["solutions_pdf"] == "ORIGINAL-DEMO-CONTENT-NO-PDF"
        for problem in problems
    )
    assert not list(PROJECT_ROOT.rglob("*.pdf"))


def test_every_demo_image_exists_and_decodes(problems):
    paths = []
    for problem in problems:
        paths.extend(image["path"] for image in problem["question_images"])
        paths.extend(choice["image"]["path"] for choice in problem["choices"])

    assert len(paths) == 48
    assert len(set(paths)) == len(paths)
    for path in paths:
        with Image.open(STATIC_ROOT / path) as image:
            image.verify()


def test_home_catalog_and_exam_filters_load(client):
    assert client.get("/").status_code == 200

    catalog = client.get("/api/problems/catalog").get_json()
    assert len(catalog) == 8
    assert all("correct_answers" not in item for item in catalog)

    exams = client.get("/api/exams").get_json()
    assert {exam["label"] for exam in exams} == {
        "2099 Exam Demo A",
        "2099 Exam Demo B",
    }

    filtered = client.get(
        "/api/problems/random", query_string={"exam": "2099-demo a"}
    )
    assert filtered.status_code == 200
    assert filtered.get_json()["exam_version"] == "Demo A"


def test_problem_response_hides_answer_and_serves_assets(client, problems):
    for problem in problems:
        response = client.get(f"/api/problems/{problem['id']}")
        public_problem = response.get_json()
        assert response.status_code == 200
        assert "correct_answers" not in public_problem
        for image in public_problem["question_images"]:
            assert client.get(f"/static/{image['path']}").status_code == 200
        for choice in public_problem["choices"]:
            assert client.get(f"/static/{choice['image']['path']}").status_code == 200


def test_grading_accepts_correct_and_rejects_incorrect_answers(client, problems):
    for problem in problems:
        correct_answer = problem["correct_answers"][0]
        incorrect_answer = next(label for label in "ABCDE" if label != correct_answer)

        correct = client.post(
            "/api/answers",
            json={"problem_id": problem["id"], "answer": correct_answer},
        ).get_json()
        incorrect = client.post(
            "/api/answers",
            json={"problem_id": problem["id"], "answer": incorrect_answer},
        ).get_json()

        assert correct["correct"] is True
        assert incorrect["correct"] is False
        assert correct["correct_answers"] == [correct_answer]


def test_developer_routes_are_disabled_by_default(client):
    assert client.get("/manage").status_code == 404
    assert client.get("/api/manage/problems").status_code == 404
    assert client.get("/review").status_code == 404
    assert client.get("/api/review/problems").status_code == 404


def test_progress_script_uses_browser_local_storage():
    script = (STATIC_ROOT / "js" / "progress_store.js").read_text(encoding="utf-8")

    assert 'const STORAGE_KEY = "fmaTrainer.progress"' in script
    assert "window.localStorage" in script
    assert "recordAttempt" in script
    assert "clearProgress" in script
