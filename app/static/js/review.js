const form = document.querySelector("#review-form");
const message = document.querySelector("#page-message");
const picker = document.querySelector("#problem-picker");
const previousButton = document.querySelector("#previous-problem");
const nextButton = document.querySelector("#next-problem");
const verifyButton = document.querySelector("#verify-problem");
const unlockButton = document.querySelector("#unlock-problem");

let problems = [];
let currentIndex = 0;
let verifiedRecordUnlocked = false;

async function loadProblems(preferredId = null) {
  showMessage("Loading…");
  try {
    const response = await fetch("/api/review/problems");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not load generated problems.");
    }

    problems = data.problems;
    document.querySelector("#review-counts").textContent =
      `${data.counts.needs_review} need review · ${data.counts.verified} verified`;

    if (problems.length === 0) {
      form.hidden = true;
      showMessage("There are no generated problems to review.");
      return;
    }

    const requestedId = preferredId || new URLSearchParams(location.search).get("problem");
    const requestedIndex = problems.findIndex((problem) => problem.id === requestedId);
    currentIndex = requestedIndex >= 0 ? requestedIndex : 0;
    buildPicker();
    renderCurrentProblem();
    showMessage("");
  } catch (error) {
    form.hidden = true;
    showMessage(error.message, "error");
  }
}

function buildPicker() {
  picker.replaceChildren();
  problems.forEach((problem, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${problem.id} — ${problem.review_status.replace("_", " ")}`;
    picker.append(option);
  });
}

function renderCurrentProblem() {
  const problem = problems[currentIndex];
  verifiedRecordUnlocked = false;
  picker.value = String(currentIndex);
  history.replaceState(null, "", `/review?problem=${encodeURIComponent(problem.id)}`);

  const version = problem.exam_version || "no printed version";
  document.querySelector("#problem-heading").textContent =
    `${problem.year} F=ma · ${version} · Problem ${problem.problem_number}`;
  document.querySelector("#record-status").textContent =
    `ID: ${problem.id} · Status: ${problem.review_status.replace("_", " ")}`;
  document.querySelector("#question-text").value = problem.question;
  document.querySelector("#diagram-status").value = problem.diagram_status;

  renderSourceLinks(problem.source);
  renderDiagrams(problem.diagrams || []);
  renderChoices(problem.choices);
  renderAnswers(problem.correct_answers);
  renderWarnings(problem.review_notes || []);

  previousButton.disabled = currentIndex === 0;
  nextButton.disabled = currentIndex === problems.length - 1;
  form.hidden = false;
  updateVerifiedLock();
}

function renderSourceLinks(source) {
  const container = document.querySelector("#source-links");
  container.replaceChildren();
  addSourceLinks(container, "Exam", source.exam_pdf, source.exam_pages);
  addSourceLinks(container, "Solutions", source.solutions_pdf, source.solutions_pages);
}

function addSourceLinks(container, label, filename, pages) {
  pages.forEach((page) => {
    const link = document.createElement("a");
    link.href = `/review/source/${encodeURIComponent(filename)}#page=${page}`;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = `${label}: ${filename}, PDF page ${page}`;
    container.append(link);
  });
}

function renderDiagrams(diagrams) {
  const container = document.querySelector("#stem-diagrams");
  container.replaceChildren();
  diagrams.forEach((diagram) => container.append(createSourceImage(diagram)));
}

function renderChoices(choices) {
  const container = document.querySelector("#choice-editors");
  container.replaceChildren();

  choices.forEach((choice) => {
    const row = document.createElement("div");
    row.className = "choice-row";

    const label = document.createElement("span");
    label.className = "choice-label";
    label.textContent = choice.label;

    const content = document.createElement("div");
    content.className = "choice-content";
    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.dataset.choiceLabel = choice.label;
    textarea.value = choice.text || "";
    textarea.setAttribute("aria-label", `Choice ${choice.label} text`);
    textarea.placeholder = choice.image ? "Graphical choice (text is optional)" : "Choice text";
    content.append(textarea);
    if (choice.image) {
      content.append(createSourceImage(choice.image));
    }

    row.append(label, content);
    container.append(row);
  });
}

function createSourceImage(image) {
  const element = document.createElement("img");
  element.className = "source-image";
  element.src = `/static/${image.path}`;
  element.alt = image.alt_text;
  element.loading = "lazy";
  return element;
}

function renderAnswers(correctAnswers) {
  const container = document.querySelector("#answer-editors");
  container.replaceChildren();
  ["A", "B", "C", "D", "E"].forEach((label) => {
    const wrapper = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "correct-answer";
    checkbox.value = label;
    checkbox.checked = correctAnswers.includes(label);
    wrapper.append(checkbox, ` ${label}`);
    container.append(wrapper);
  });
}

function renderWarnings(warnings) {
  const list = document.querySelector("#parsing-warnings");
  list.replaceChildren();
  if (warnings.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No parsing warnings.";
    list.append(item);
    return;
  }
  warnings.forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    list.append(item);
  });
}

function updateVerifiedLock() {
  const isVerified = problems[currentIndex].review_status === "verified";
  const locked = isVerified && !verifiedRecordUnlocked;
  form.querySelectorAll("textarea, input, select").forEach((control) => {
    control.disabled = locked;
  });
  document.querySelector("#save-problem").disabled = locked;
  verifyButton.hidden = isVerified;
  unlockButton.hidden = !locked;
}

function collectEdits() {
  return {
    question: document.querySelector("#question-text").value,
    choices: [...document.querySelectorAll("[data-choice-label]")].map((textarea) => ({
      label: textarea.dataset.choiceLabel,
      text: textarea.value || null,
    })),
    correct_answers: [...document.querySelectorAll('[name="correct-answer"]:checked')]
      .map((checkbox) => checkbox.value),
    diagram_status: document.querySelector("#diagram-status").value,
    allow_verified_edit: verifiedRecordUnlocked,
  };
}

async function saveCurrentProblem() {
  const problem = problems[currentIndex];
  const response = await fetch(`/api/review/problems/${encodeURIComponent(problem.id)}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(collectEdits()),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Could not save this problem.");
  }
  return data.problem;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const savedProblem = await saveCurrentProblem();
    await loadProblems(savedProblem.id);
    showMessage("Changes saved.", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
});

verifyButton.addEventListener("click", async () => {
  const problem = problems[currentIndex];
  try {
    // Save first so the verified record includes the latest visible edits.
    await saveCurrentProblem();
    const response = await fetch(
      `/api/review/problems/${encodeURIComponent(problem.id)}/verify`,
      {method: "POST"},
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not verify this problem.");
    }
    await loadProblems();
    showMessage(`${problem.id} marked verified. Showing the next priority problem.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
});

unlockButton.addEventListener("click", () => {
  const confirmed = window.confirm(
    "This record is already verified. Editing it will return it to needs_review. Continue?",
  );
  if (confirmed) {
    verifiedRecordUnlocked = true;
    updateVerifiedLock();
    showMessage("Verified record unlocked. Saving any edit will require re-verification.");
  }
});

picker.addEventListener("change", () => {
  currentIndex = Number(picker.value);
  renderCurrentProblem();
  showMessage("");
});

previousButton.addEventListener("click", () => {
  currentIndex -= 1;
  renderCurrentProblem();
  showMessage("");
});

nextButton.addEventListener("click", () => {
  currentIndex += 1;
  renderCurrentProblem();
  showMessage("");
});

function showMessage(text, type = "") {
  message.textContent = text;
  message.className = `message ${type}`.trim();
}

loadProblems();
