# F=ma Trainer — Public Demo

A Flask practice application that demonstrates an image-first workflow for
multiple-choice introductory mechanics problems. This public portfolio edition
contains eight original demo questions and no official exam content.

The complete private trainer supports 575 problems across 23 historical exam
versions. Those exam questions, answer keys, images, solutions, and PDFs are
not distributed in this repository.

## Features

- Random problem selection and demo-set filtering
- Five image-rendered answer choices per problem
- Server-authoritative grading with immediate feedback
- Random, Unattempted, and Incorrect practice modes
- Browser-local progress and progress-by-exam summaries
- Responsive interface with accessible text fallbacks
- Developer management and review routes disabled by default

## Architecture

- `app/` contains the Flask application, routes, templates, CSS, and vanilla
  JavaScript frontend.
- `data/problems.json` is the validated schema-version-2 demo collection.
- `app/static/problem_images/demo/` contains reproducible images generated
  from the original demo questions.
- `scripts/generate_demo_dataset.py` regenerates the demo JSON and images.
- `tests/` covers dataset integrity, assets, routes, grading, filters, progress
  storage, and developer-route isolation.

Flask serves the page and JSON APIs. The browser chooses eligible problems,
renders their images, submits answers to Flask, and stores practice progress in
`localStorage`. Correct answers are not included in problem responses; they are
returned only after an answer is submitted.

## Run locally

Python 3.12 is recommended.

```bash
git clone <repository-url>
cd fma-trainer-public
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Flask's built-in server is for local development,
not public deployment.

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Tests

```bash
python -m pytest
```

To regenerate the original demo dataset and all 48 demo images:

```bash
python scripts/generate_demo_dataset.py
```

## Production command

The application exposes a Flask factory and includes Gunicorn:

```bash
gunicorn --bind 0.0.0.0:$PORT 'app:create_app()'
```

Leave `FMA_MANAGEMENT_MODE` unset or set it to `0` publicly. `/manage` and
`/review` are local developer tools and must not be enabled on a public site.
Normal public practice requires no server filesystem writes.

For local image-management development only, start with:

```bash
FMA_MANAGEMENT_MODE=1 python app.py
```

The image manager can inspect the included demo collection. The retained import
review code expects separate local review data, which is intentionally not part
of this public demonstration.

## Demo limitations

- The included questions are deliberately small, original examples rather
  than historical competition problems.
- Progress stays in the current browser, requires no account, does not sync
  between devices, and is removed when site data is cleared.
- Source fields in the JSON use `ORIGINAL-DEMO-CONTENT-NO-PDF` to satisfy the
  shared schema without pretending that a source PDF exists.

## Attribution and independence

F=ma is part of the U.S. Physics Team selection process organized by the
American Association of Physics Teachers. Official historical materials are
available from the [AAPT past-exams archive](https://www.aapt.org/physicsteam/PT-exams.cfm).

This is an independent, unofficial project. It is not affiliated with or
endorsed by AAPT. No AAPT questions, answer keys, exam images, solutions, or
PDFs are included here.

## License

The original source code is available under the [MIT License](LICENSE). The
license does not grant rights to third-party names, marks, or materials.
