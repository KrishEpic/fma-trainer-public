const problemMeta = document.querySelector("#problem-meta");
const problemHeading = document.querySelector("#problem-heading");
const questionImages = document.querySelector("#question-images");
const examSelect = document.querySelector("#exam-select");
const practiceMode = document.querySelector("#practice-mode");
const answerForm = document.querySelector("#answer-form");
const choicesContainer = document.querySelector("#choices");
const submitButton = document.querySelector("#submit-button");
const newProblemButton = document.querySelector("#new-problem-button");
const result = document.querySelector("#result");
const problemCard = document.querySelector(".problem-card");
const progressSummary = document.querySelector("#progress-summary");
const toggleProgressButton = document.querySelector("#toggle-progress");
const progressDetails = document.querySelector("#progress-details");
const progressAttempted = document.querySelector("#progress-attempted");
const progressCompletion = document.querySelector("#progress-completion");
const progressTotalAttempts = document.querySelector("#progress-total-attempts");
const progressCorrect = document.querySelector("#progress-correct");
const progressIncorrect = document.querySelector("#progress-incorrect");
const progressAccuracy = document.querySelector("#progress-accuracy");
const progressByExam = document.querySelector("#progress-by-exam");
const resetProgressButton = document.querySelector("#reset-progress");
const resetConfirmation = document.querySelector("#reset-confirmation");
const confirmResetButton = document.querySelector("#confirm-reset");
const cancelResetButton = document.querySelector("#cancel-reset");
const progressStatus = document.querySelector("#progress-status");

let currentProblemId = null;
let submissionInProgress = false;
let problemCatalog = null;
let problemLoadNumber = 0;

async function loadProblem() {
  const thisLoadNumber = ++problemLoadNumber;
  const previousProblemId = currentProblemId;
  let newProblemAvailable = true;

  resetInteractionState();
  choicesContainer.replaceChildren();
  questionImages.replaceChildren();
  questionImages.hidden = true;
  choicesContainer.disabled = true;
  newProblemButton.disabled = true;
  problemCard.classList.add("is-loading");
  problemCard.setAttribute("aria-busy", "true");
  problemMeta.textContent = "Loading a problem…";
  problemHeading.textContent = "Please wait.";
  problemHeading.classList.add("visually-hidden");

  try {
    if (problemCatalog === null) {
      await loadCatalog();
    }
    if (thisLoadNumber !== problemLoadNumber) {
      return;
    }

    const eligibleProblems = getEligibleProblems();
    if (eligibleProblems.length === 0) {
      currentProblemId = null;
      newProblemAvailable = false;
      renderEmptyState();
      return;
    }

    const choices = eligibleProblems.length > 1
      ? eligibleProblems.filter((problem) => problem.id !== previousProblemId)
      : eligibleProblems;
    const selectedProblem = choices[Math.floor(Math.random() * choices.length)];
    const response = await fetch(
      `/api/problems/${encodeURIComponent(selectedProblem.id)}`,
    );
    const problem = await response.json();

    if (!response.ok) {
      throw new Error(problem.error || "The problem could not be loaded.");
    }
    if (thisLoadNumber !== problemLoadNumber) {
      return;
    }

    currentProblemId = problem.id;
    const examName = problem.exam_version
      ? `Exam ${problem.exam_version}`
      : "F=ma Exam";
    problemMeta.textContent = `${problem.year} · ${examName} · Problem ${problem.problem_number}`;
    problemHeading.textContent = problem.question;
    problemHeading.classList.add("visually-hidden");
    renderQuestionImages(problem.question_images);

    for (const choice of problem.choices) {
      choicesContainer.append(createChoice(choice));
    }

    choicesContainer.disabled = false;
  } catch (error) {
    if (thisLoadNumber !== problemLoadNumber) {
      return;
    }
    currentProblemId = null;
    problemMeta.textContent = "Unable to load a problem";
    problemHeading.textContent = "Please try again.";
    problemHeading.classList.remove("visually-hidden");
    newProblemButton.textContent = "Try Again";
    setResult(error.message, "error");
  } finally {
    if (thisLoadNumber === problemLoadNumber) {
      problemCard.classList.remove("is-loading");
      problemCard.removeAttribute("aria-busy");
      newProblemButton.disabled = !newProblemAvailable;
    }
  }
}

async function loadCatalog() {
  const response = await fetch("/api/problems/catalog");
  const catalog = await response.json();

  if (!response.ok) {
    throw new Error(catalog.error || "The problem catalog could not be loaded.");
  }
  if (!isValidCatalog(catalog)) {
    throw new Error("The problem catalog response was invalid.");
  }

  problemCatalog = catalog;
  practiceMode.disabled = false;
  renderProgress();
}

function isValidCatalog(catalog) {
  return (
    Array.isArray(catalog) &&
    catalog.length > 0 &&
    catalog.every(
      (problem) =>
        problem !== null &&
        typeof problem === "object" &&
        typeof problem.id === "string" &&
        typeof problem.exam_key === "string",
    )
  );
}

function getEligibleProblems() {
  const progressProblems = getLocalProgressProblems();

  return problemCatalog.filter((problem) => {
    if (examSelect.value && problem.exam_key !== examSelect.value) {
      return false;
    }

    const hasProgress = Object.prototype.hasOwnProperty.call(
      progressProblems,
      problem.id,
    );
    if (practiceMode.value === "unattempted") {
      return !hasProgress;
    }
    if (practiceMode.value === "incorrect") {
      return hasProgress && progressProblems[problem.id].lastCorrect === false;
    }
    return true;
  });
}

function getLocalProgressProblems() {
  try {
    return window.FmaProgress?.getProgress().problems || {};
  } catch (_error) {
    // If optional browser storage fails, Random still works and the other
    // modes behave as though no local attempts have been recorded.
    return {};
  }
}

function calculateProgress() {
  const progressProblems = getLocalProgressProblems();
  const overall = {
    totalProblems: problemCatalog.length,
    attemptedProblems: 0,
    totalAttempts: 0,
    correctAttempts: 0,
    incorrectAttempts: 0,
  };
  const examsByKey = new Map();

  for (const problem of problemCatalog) {
    if (!examsByKey.has(problem.exam_key)) {
      examsByKey.set(problem.exam_key, {
        year: problem.year,
        examVersion: problem.exam_version,
        totalProblems: 0,
        attemptedProblems: 0,
        totalAttempts: 0,
        correctAttempts: 0,
      });
    }

    const exam = examsByKey.get(problem.exam_key);
    exam.totalProblems += 1;

    if (!Object.prototype.hasOwnProperty.call(progressProblems, problem.id)) {
      continue;
    }

    const record = progressProblems[problem.id];
    overall.attemptedProblems += 1;
    overall.totalAttempts += record.attempts;
    overall.correctAttempts += record.correct;
    overall.incorrectAttempts += record.incorrect;
    exam.attemptedProblems += 1;
    exam.totalAttempts += record.attempts;
    exam.correctAttempts += record.correct;
  }

  const exams = Array.from(examsByKey.values()).sort((first, second) => {
    if (first.year !== second.year) {
      return second.year - first.year;
    }
    return (second.examVersion || "").localeCompare(first.examVersion || "");
  });

  return { overall, exams };
}

function renderProgress() {
  if (problemCatalog === null) {
    return;
  }

  const { overall, exams } = calculateProgress();
  const completion = formatPercentage(
    overall.attemptedProblems,
    overall.totalProblems,
  );
  const accuracy = formatAccuracy(
    overall.correctAttempts,
    overall.totalAttempts,
  );

  progressSummary.textContent =
    `${overall.attemptedProblems} / ${overall.totalProblems} attempted · ` +
    `${completion} complete · Accuracy ${accuracy}`;
  progressAttempted.textContent =
    `${overall.attemptedProblems} / ${overall.totalProblems}`;
  progressCompletion.textContent = completion;
  progressTotalAttempts.textContent = overall.totalAttempts;
  progressCorrect.textContent = overall.correctAttempts;
  progressIncorrect.textContent = overall.incorrectAttempts;
  progressAccuracy.textContent = accuracy;

  const rows = exams.map((exam) => {
    const row = document.createElement("tr");
    const examName = document.createElement("th");
    examName.scope = "row";
    examName.textContent = exam.examVersion
      ? `${exam.year} Exam ${exam.examVersion}`
      : `${exam.year} F=ma`;
    row.append(
      examName,
      createProgressCell(
        `${exam.attemptedProblems} / ${exam.totalProblems}`,
      ),
      createProgressCell(
        formatPercentage(exam.attemptedProblems, exam.totalProblems),
      ),
      createProgressCell(exam.totalAttempts),
      createProgressCell(
        formatAccuracy(exam.correctAttempts, exam.totalAttempts),
      ),
    );
    return row;
  });
  progressByExam.replaceChildren(...rows);
}

function createProgressCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function formatPercentage(part, whole) {
  if (whole === 0) {
    return "0%";
  }
  const rounded = Math.round((part / whole) * 1000) / 10;
  return `${rounded.toFixed(Number.isInteger(rounded) ? 0 : 1)}%`;
}

function formatAccuracy(correct, attempts) {
  return attempts === 0 ? "—" : formatPercentage(correct, attempts);
}

function renderEmptyState() {
  const scope = examSelect.value ? "this exam" : "this selection";
  const message = practiceMode.value === "unattempted"
    ? `You have attempted every problem in ${scope}.`
    : `You have no previously incorrect problems in ${scope}.`;

  problemMeta.textContent = "Practice selection";
  problemHeading.textContent = "No problems available";
  problemHeading.classList.remove("visually-hidden");
  choicesContainer.disabled = true;
  submitButton.hidden = true;
  setResult(
    `${message} Choose another exam or practice mode to continue.`,
    "",
  );
}

function renderQuestionImages(images) {
  questionImages.replaceChildren();
  for (const image of images) {
    // The hidden text heading already gives screen readers the question text.
    questionImages.append(createProblemImage(image, ""));
  }
  questionImages.hidden = images.length === 0;
}

async function loadExams() {
  try {
    const response = await fetch("/api/exams");
    const exams = await response.json();

    if (!response.ok) {
      throw new Error(exams.error || "The exam list could not be loaded.");
    }

    for (const exam of exams) {
      const option = document.createElement("option");
      option.value = exam.key;
      option.textContent = exam.label;
      examSelect.append(option);
    }
    examSelect.disabled = false;
  } catch (error) {
    setResult(error.message, "error");
  }
}

function createChoice(choice) {
  const choiceLabel = document.createElement("label");
  choiceLabel.className = "choice";

  const radio = document.createElement("input");
  radio.type = "radio";
  radio.name = "answer";
  radio.value = choice.label;
  radio.setAttribute(
    "aria-label",
    `${choice.label}. ${choice.text || choice.image.alt_text}`,
  );

  const choiceContent = document.createElement("span");
  choiceContent.className = "choice-content";

  if (choice.image) {
    choiceContent.append(createProblemImage(choice.image));
  } else if (choice.text) {
    const choiceLabelText = document.createElement("strong");
    choiceLabelText.textContent = `${choice.label}.`;
    const choiceText = document.createElement("span");
    choiceText.className = "choice-text";
    choiceText.textContent = choice.text;
    choiceContent.append(choiceLabelText, choiceText);
  }

  choiceLabel.append(radio, choiceContent);
  return choiceLabel;
}

function resetInteractionState() {
  answerForm.reset();
  for (const choice of choicesContainer.querySelectorAll(".choice")) {
    choice.classList.remove("is-selected", "is-correct", "is-incorrect");
    choice.querySelector(".choice-status")?.remove();
  }
  submitButton.hidden = false;
  submitButton.disabled = true;
  newProblemButton.textContent = "New Problem";
  newProblemButton.classList.add("secondary");
  setResult("", "");
}

function updateSelectedChoice(selectedRadio) {
  for (const choice of choicesContainer.querySelectorAll(".choice")) {
    choice.classList.toggle("is-selected", choice.contains(selectedRadio));
  }
  submitButton.disabled = false;
}

function addChoiceStatus(choice, message) {
  const status = document.createElement("span");
  status.className = "choice-status";
  status.textContent = message;
  choice.append(status);
}

function renderGradingResult(selectedAnswer, answerResult) {
  const correctAnswers = new Set(answerResult.correct_answers);

  for (const choice of choicesContainer.querySelectorAll(".choice")) {
    const radio = choice.querySelector('input[name="answer"]');
    const isSelected = radio.value === selectedAnswer;
    const isCorrect = correctAnswers.has(radio.value);

    if (isCorrect) {
      choice.classList.add("is-correct");
      addChoiceStatus(
        choice,
        isSelected ? "Your answer · Correct" : "Correct answer",
      );
    } else if (isSelected) {
      choice.classList.add("is-incorrect");
      addChoiceStatus(choice, "Your answer");
    }
  }

  submitButton.hidden = true;
  newProblemButton.classList.remove("secondary");
}

function createProblemImage(imageData, altText = imageData.alt_text) {
  const image = document.createElement("img");
  const encodedPath = imageData.path.split("/").map(encodeURIComponent).join("/");
  image.src = `/static/${encodedPath}`;
  image.alt = altText;
  image.className = "problem-image";
  image.loading = "lazy";
  return image;
}

choicesContainer.addEventListener("change", (event) => {
  if (event.target.matches('input[name="answer"]')) {
    updateSelectedChoice(event.target);
  }
});

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (submissionInProgress) {
    return;
  }

  const selectedAnswer = new FormData(answerForm).get("answer");
  if (!selectedAnswer || !currentProblemId) {
    setResult("Select an answer before submitting.", "error");
    return;
  }

  const submittedProblemId = currentProblemId;
  submissionInProgress = true;
  submitButton.disabled = true;
  newProblemButton.disabled = true;
  examSelect.disabled = true;
  practiceMode.disabled = true;

  try {
    const response = await fetch("/api/answers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_id: submittedProblemId,
        answer: selectedAnswer,
      }),
    });
    const answerResult = await response.json();

    if (!response.ok) {
      throw new Error(answerResult.error || "The answer could not be checked.");
    }
    if (!isValidGradingResult(answerResult)) {
      throw new Error("The answer-checking response was invalid.");
    }

    // Saving progress is optional. Browser storage errors must not hide a valid
    // grading result or interrupt practice.
    try {
      const progressRecorded = window.FmaProgress?.recordAttempt(
        submittedProblemId,
        answerResult.correct,
      );
      if (progressRecorded) {
        renderProgress();
        setProgressStatus("", "");
      }
    } catch (_error) {
      // The progress store normally handles these errors itself. This final
      // guard also protects practice if the optional script fails unexpectedly.
    }

    choicesContainer.disabled = true;
    renderGradingResult(selectedAnswer, answerResult);
    const message = answerResult.correct
      ? `Correct. The answer is ${answerResult.correct_answer}.`
      : `Incorrect. You selected ${selectedAnswer}. The correct answer is ${answerResult.correct_answer}.`;
    setResult(message, answerResult.correct ? "correct" : "incorrect");
  } catch (error) {
    submitButton.disabled = false;
    setResult(error.message, "error");
  } finally {
    submissionInProgress = false;
    newProblemButton.disabled = false;
    examSelect.disabled = false;
    practiceMode.disabled = problemCatalog === null;
  }
});

newProblemButton.addEventListener("click", loadProblem);
examSelect.addEventListener("change", loadProblem);
practiceMode.addEventListener("change", loadProblem);

toggleProgressButton.addEventListener("click", () => {
  const opening = progressDetails.hidden;
  progressDetails.hidden = !opening;
  toggleProgressButton.setAttribute("aria-expanded", String(opening));
  toggleProgressButton.textContent = opening ? "Hide Progress" : "View Progress";
  if (opening) {
    renderProgress();
  } else {
    hideResetConfirmation();
  }
});

resetProgressButton.addEventListener("click", () => {
  setProgressStatus("", "");
  resetConfirmation.hidden = false;
  confirmResetButton.focus();
});

cancelResetButton.addEventListener("click", () => {
  hideResetConfirmation();
  resetProgressButton.focus();
});

confirmResetButton.addEventListener("click", () => {
  if (submissionInProgress) {
    setProgressStatus("Wait for the current answer to finish grading.", "error");
    return;
  }

  let progressCleared = false;
  try {
    progressCleared = window.FmaProgress?.clearProgress() === true;
  } catch (_error) {
    progressCleared = false;
  }

  if (!progressCleared) {
    setProgressStatus(
      "Progress could not be reset. Your existing progress was not changed.",
      "error",
    );
    return;
  }

  hideResetConfirmation();
  practiceMode.value = "random";
  renderProgress();
  setProgressStatus("Practice progress was reset in this browser.", "success");

  if (currentProblemId) {
    resetInteractionState();
    choicesContainer.disabled = false;
  } else {
    loadProblem();
  }
  resetProgressButton.focus();
});

function hideResetConfirmation() {
  resetConfirmation.hidden = true;
}

function setProgressStatus(message, className) {
  progressStatus.textContent = message;
  progressStatus.className = `progress-status ${className}`.trim();
}

function setResult(message, className) {
  result.textContent = message;
  result.className = `result ${className}`.trim();
}

function isValidGradingResult(answerResult) {
  return (
    answerResult !== null &&
    typeof answerResult === "object" &&
    typeof answerResult.correct === "boolean" &&
    typeof answerResult.correct_answer === "string" &&
    answerResult.correct_answer.length > 0 &&
    Array.isArray(answerResult.correct_answers) &&
    answerResult.correct_answers.length > 0 &&
    answerResult.correct_answers.every(
      (answer) => typeof answer === "string" && /^[A-E]$/.test(answer),
    )
  );
}

loadExams();
loadProblem();
