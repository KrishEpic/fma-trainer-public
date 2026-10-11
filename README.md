# F=ma Trainer

I built this web app to make practicing for the F=ma physics exam easier. Instead of opening old exam PDFs, keeping track of question numbers, and checking answers separately, I wanted a way to practice random problems and see which ones I kept getting wrong.

The full version of the trainer contains 575 problems from 23 past exam versions. This public repository contains the application code and eight original sample problems. I left out the actual exam questions, images, and PDFs.

<img width="1344" height="1066" alt="Screenshot 2026-10-11 at 1 19 03 PM" src="https://github.com/user-attachments/assets/3dd19ad5-1cdf-4d5a-8dfd-d20fa3ed1fdb" />

## Features

- **Random practice:** Get a random problem or choose an exam.
- **Practice missed questions:** Switch between Random, Unattempted, and Incorrect modes.
- **Answer checking:** Submit an answer and immediately see whether it's correct.
- **Progress tracking:** See how many problems you've attempted, your accuracy, and your progress on each exam.
- **Image-based questions:** Problems and answer choices are displayed as images, so diagrams and mathematical notation stay intact.
- **Local storage:** Your progress is saved in your browser without needing an account.

## How it works

The backend uses Python and Flask. Problems are stored in a JSON file, and the frontend uses HTML, CSS, and JavaScript.

When you request a problem, Flask sends the question and its five answer choices to the browser without revealing the correct answer. The browser sends your selection back to the server for grading.

Progress is stored using the browser's `localStorage`, so you can close the page and pick up where you left off.

I also wrote a script to generate the sample problems and their images. You can find it at `scripts/generate_demo_dataset.py`.

## Running the app

You'll need Python 3.12.

Clone the repository and install the dependencies:

```bash
git clone https://github.com/KrishEpic/fma-trainer-public.git
cd fma-trainer-public

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

For Windows PowerShell, use `.venv\Scripts\Activate.ps1` to activate the virtual environment.

## Tests

Run the tests with:

```bash
python -m pytest
```

To regenerate the eight demo problems and their images:

```bash
python scripts/generate_demo_dataset.py
```

## Deploying

The app can also run with Gunicorn:

```bash
gunicorn --bind 0.0.0.0:$PORT 'app:create_app()'
```

The repository includes developer tools for reviewing problem images, but these are disabled by default. Keep `FMA_MANAGEMENT_MODE` unset or set to `0` on public deployments.

## About this public version

The eight sample questions are original introductory mechanics problems, divided into two fictional exam sets for testing the filtering system.

The full trainer uses historical F=ma exam material, which is not included here. You can find official past exams on the [AAPT website](https://www.aapt.org/physicsteam/PT-exams.cfm).

Progress is saved only in your current browser. It doesn't sync across devices.

This is an independent project and is not affiliated with or endorsed by the American Association of Physics Teachers.

## License

The original source code is licensed under the [MIT License](LICENSE). Third-party material and trademarks are not covered.
