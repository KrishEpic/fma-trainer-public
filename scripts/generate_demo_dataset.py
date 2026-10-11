"""Generate the original public-demo problems and their image assets."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "problems.json"
IMAGE_DIRECTORY = PROJECT_ROOT / "app" / "static" / "problem_images" / "demo"
PUBLIC_IMAGE_DIRECTORY = "problem_images/demo"
SOURCE_MARKER = "ORIGINAL-DEMO-CONTENT-NO-PDF"

DEMO_PROBLEMS = (
    {
        "id": "demo-a-01",
        "version": "Demo A",
        "number": 1,
        "question": (
            "A bicycle starts from rest and accelerates uniformly at 2 m/s^2 "
            "for 4 s. What is its final speed?"
        ),
        "choices": ("2 m/s", "4 m/s", "6 m/s", "8 m/s", "16 m/s"),
        "answer": "D",
    },
    {
        "id": "demo-a-02",
        "version": "Demo A",
        "number": 2,
        "question": (
            "A 6 kg crate experiences a constant net horizontal force of 18 N. "
            "What is the crate's acceleration?"
        ),
        "choices": ("0.33 m/s^2", "3 m/s^2", "6 m/s^2", "12 m/s^2", "108 m/s^2"),
        "answer": "B",
    },
    {
        "id": "demo-a-03",
        "version": "Demo A",
        "number": 3,
        "question": (
            "A runner moves in a straight line at a constant speed of 5 m/s for "
            "12 s. How far does the runner travel?"
        ),
        "choices": ("17 m", "50 m", "60 m", "72 m", "120 m"),
        "answer": "C",
    },
    {
        "id": "demo-a-04",
        "version": "Demo A",
        "number": 4,
        "question": (
            "Near Earth's surface, take g = 10 m/s^2. What is the weight of a "
            "2.5 kg backpack?"
        ),
        "choices": ("0.25 N", "4 N", "12.5 N", "25 N", "250 N"),
        "answer": "D",
    },
    {
        "id": "demo-b-01",
        "version": "Demo B",
        "number": 1,
        "question": (
            "A ball is thrown straight upward at 20 m/s. Ignoring air resistance "
            "and taking g = 10 m/s^2, how long does it take to reach its highest point?"
        ),
        "choices": ("1 s", "2 s", "4 s", "10 s", "20 s"),
        "answer": "B",
    },
    {
        "id": "demo-b-02",
        "version": "Demo B",
        "number": 2,
        "question": (
            "A 4 kg cart moves east at 3 m/s. What is the magnitude of its momentum?"
        ),
        "choices": ("1.3 kg m/s", "7 kg m/s", "12 kg m/s", "24 kg m/s", "36 kg m/s"),
        "answer": "C",
    },
    {
        "id": "demo-b-03",
        "version": "Demo B",
        "number": 3,
        "question": (
            "A constant 15 N force pushes a box 4 m in the same direction as the "
            "force. How much work does the force do?"
        ),
        "choices": ("3.75 J", "19 J", "45 J", "60 J", "75 J"),
        "answer": "D",
    },
    {
        "id": "demo-b-04",
        "version": "Demo B",
        "number": 4,
        "question": "What is the kinetic energy of a 2 kg object moving at 5 m/s?",
        "choices": ("5 J", "10 J", "25 J", "50 J", "100 J"),
        "answer": "C",
    },
)


def _font(size: int, *, bold: bool = False):
    names = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default(size=size)


def _wrapped_lines(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _render_text_card(path: Path, heading: str, text: str, *, width: int) -> None:
    heading_font = _font(18, bold=True)
    body_font = _font(32)
    draft = Image.new("RGB", (width, 300), "white")
    draft_draw = ImageDraw.Draw(draft)
    lines = _wrapped_lines(draft_draw, text, body_font, width - 80)
    line_height = 45
    height = 38 + 34 + len(lines) * line_height + 40

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 8), fill="#2457a7")
    draw.text((40, 28), heading, font=heading_font, fill="#52617a")
    y = 70
    for line in lines:
        draw.text((40, y), line, font=body_font, fill="#172033")
        y += line_height

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _image_record(filename: str, alt_text: str) -> dict[str, str]:
    return {
        "path": f"{PUBLIC_IMAGE_DIRECTORY}/{filename}",
        "alt_text": alt_text,
    }


def build_dataset() -> dict:
    records = []
    expected_images = set()
    for item in DEMO_PROBLEMS:
        question_filename = f"{item['id']}-question.png"
        expected_images.add(question_filename)
        _render_text_card(
            IMAGE_DIRECTORY / question_filename,
            "ORIGINAL DEMO PROBLEM",
            item["question"],
            width=1100,
        )

        choices = []
        for label, choice_text in zip("ABCDE", item["choices"]):
            choice_filename = f"{item['id']}-choice-{label.lower()}.png"
            expected_images.add(choice_filename)
            _render_text_card(
                IMAGE_DIRECTORY / choice_filename,
                f"CHOICE {label}",
                choice_text,
                width=760,
            )
            choices.append(
                {
                    "label": label,
                    "text": choice_text,
                    "image": _image_record(
                        choice_filename, f"Choice {label}: {choice_text}"
                    ),
                }
            )

        records.append(
            {
                "id": item["id"],
                "year": 2099,
                "exam_version": item["version"],
                "problem_number": item["number"],
                "question": item["question"],
                "question_images": [
                    _image_record(question_filename, item["question"])
                ],
                "choices": choices,
                "diagrams": [],
                "correct_answers": [item["answer"]],
                "source": {
                    "exam_pdf": SOURCE_MARKER,
                    "exam_pages": [],
                    "solutions_pdf": SOURCE_MARKER,
                    "solutions_pages": [],
                },
                "review_status": "verified",
                "review_notes": [
                    "Original mechanics question written for the public demonstration."
                ],
            }
        )

    for existing_image in IMAGE_DIRECTORY.glob("*.png"):
        if existing_image.name not in expected_images:
            existing_image.unlink()

    return {
        "schema_version": 2,
        "collection": {
            "kind": "original_public_demo",
            "notice": "Contains original demonstration questions only.",
        },
        "problems": records,
    }


def main() -> None:
    dataset = build_dataset()
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(dataset['problems'])} original demo problems.")
    print(f"Dataset: {DATA_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Images: {IMAGE_DIRECTORY.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
