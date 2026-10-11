const statusFilter = document.querySelector("#status-filter");
const yearSelect = document.querySelector("#year-select");
const examSelect = document.querySelector("#exam-select-manage");
const problemSelect = document.querySelector("#problem-select");
const previousButton = document.querySelector("#previous-problem");
const nextButton = document.querySelector("#next-problem");
const manager = document.querySelector("#problem-manager");
const message = document.querySelector("#manager-message");

let problemSummaries = [];
let currentProblemId = null;

function examKey(problem) {
  return problem.exam_version || "single";
}

function statusMatches(problem) {
  if (statusFilter.value === "all") return true;
  if (statusFilter.value === "suspicious") return problem.suspicious;
  if (statusFilter.value === "manually_replaced") {
    return problem.has_manual_override;
  }
  return problem.status === statusFilter.value;
}

function visibleProblems() {
  return problemSummaries.filter(statusMatches);
}

async function loadProblemList(preferredId = currentProblemId) {
  const response = await fetch("/api/manage/problems");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load the problem list.");
  problemSummaries = data.problems;
  buildSelectors(preferredId);
}

function buildSelectors(preferredId) {
  const available = visibleProblems();
  document.querySelector("#problem-count").textContent =
    `${available.length} of ${problemSummaries.length} problems shown`;
  if (available.length === 0) {
    manager.hidden = true;
    setMessage("No problems match this review-status filter.");
    for (const select of [yearSelect, examSelect, problemSelect]) select.replaceChildren();
    return;
  }

  const selected = available.find((problem) => problem.id === preferredId) || available[0];
  fillSelect(yearSelect, [...new Set(available.map((problem) => problem.year))], selected.year);
  fillExamSelect(available, selected);
  fillProblemSelect(available, selected);
  loadProblem(selected.id);
}

function fillSelect(select, values, selectedValue) {
  select.replaceChildren();
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    option.selected = String(value) === String(selectedValue);
    select.append(option);
  });
}

function fillExamSelect(available, selected) {
  const year = Number(yearSelect.value);
  const versions = [...new Set(
    available.filter((problem) => problem.year === year).map(examKey),
  )];
  examSelect.replaceChildren();
  versions.forEach((version) => {
    const option = document.createElement("option");
    option.value = version;
    option.textContent = version === "single" ? "Single exam" : `Exam ${version}`;
    option.selected = version === examKey(selected);
    examSelect.append(option);
  });
}

function fillProblemSelect(available, selected) {
  const year = Number(yearSelect.value);
  const version = examSelect.value;
  const matching = available.filter(
    (problem) => problem.year === year && examKey(problem) === version,
  );
  problemSelect.replaceChildren();
  matching.forEach((problem) => {
    const option = document.createElement("option");
    option.value = problem.id;
    option.textContent = `Problem ${problem.problem_number}`;
    option.selected = problem.id === selected.id;
    problemSelect.append(option);
  });
}

async function loadProblem(problemId) {
  currentProblemId = problemId;
  setMessage("Loading…");
  const response = await fetch(`/api/manage/problems/${encodeURIComponent(problemId)}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load this problem.");
  renderProblem(data);
  setMessage("");
}

function renderProblem(data) {
  const problem = data.problem;
  const version = problem.exam_version ? `Exam ${problem.exam_version}` : "Single exam";
  document.querySelector("#managed-problem-heading").textContent =
    `${problem.year} ${version} · Problem ${problem.problem_number}`;
  document.querySelector("#managed-problem-id").textContent = `Stable ID: ${problem.id}`;
  document.querySelector("#review-status").textContent = data.review.status.replaceAll("_", " ");
  document.querySelector("#preview-meta").textContent =
    `${problem.year} · ${version} · Problem ${problem.problem_number}`;
  document.querySelector("#correct-answer").textContent = problem.correct_answers.join(" or ");

  renderPublicPreview(problem);
  renderImageSlots(problem.id, data.image_slots);
  renderSource(problem.source);
  renderWarnings(problem.review_notes || []);
  renderQualityWarnings(data.quality_warnings || []);
  updateNavigation();
  manager.hidden = false;
}

function renderPublicPreview(problem) {
  const questions = document.querySelector("#preview-questions");
  questions.replaceChildren();
  problem.question_images.forEach((image) => questions.append(sourceImage(image, "problem-image")));

  const choices = document.querySelector("#preview-choices");
  choices.replaceChildren();
  problem.choices.forEach((choice) => {
    const row = document.createElement("label");
    row.className = "choice";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.disabled = true;
    radio.setAttribute("aria-label", `${choice.label}. ${choice.text || choice.image.alt_text}`);
    const content = document.createElement("span");
    content.className = "choice-content";
    content.append(sourceImage(choice.image, "problem-image"));
    row.append(radio, content);
    choices.append(row);
  });
}

function renderImageSlots(problemId, slots) {
  const container = document.querySelector("#image-slots");
  container.replaceChildren();
  slots.forEach((slot) => {
    const section = document.createElement("section");
    section.className = "image-slot";

    const heading = document.createElement("div");
    heading.className = "image-slot-header";
    const title = document.createElement("h3");
    title.textContent = slot.label;
    const origin = document.createElement("span");
    origin.className = `origin-badge ${slot.origin}`;
    origin.textContent = slot.origin;
    heading.append(title, origin);

    const currentImage = sourceImage(slot.effective_image, "image-slot-preview");
    const fullResolution = document.createElement("a");
    fullResolution.href = staticUrl(slot.effective_image.path);
    fullResolution.target = "_blank";
    fullResolution.rel = "noopener";
    fullResolution.textContent = "View full resolution";

    const quality = renderImageQuality(slot.generated_image.quality);

    const pending = document.createElement("img");
    pending.className = "image-slot-preview pending-preview";
    pending.alt = "Pending replacement preview";
    pending.hidden = true;

    const actions = document.createElement("div");
    actions.className = "image-actions";
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp";
    input.setAttribute("aria-label", `Replacement for ${slot.label}`);
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "Save replacement";
    save.disabled = true;
    input.addEventListener("change", () => {
      const file = input.files[0];
      save.disabled = !file;
      if (!file) {
        pending.hidden = true;
        pending.removeAttribute("src");
        return;
      }
      pending.src = URL.createObjectURL(file);
      pending.hidden = false;
    });
    save.addEventListener("click", () => uploadImage(problemId, slot.key, input.files[0]));
    actions.append(input, save);

    if (slot.origin === "manual") {
      const revert = document.createElement("button");
      revert.type = "button";
      revert.className = "secondary";
      revert.textContent = "Revert to Generated Image";
      revert.addEventListener("click", () => revertImage(problemId, slot.key));
      actions.append(revert);
    }

    section.append(heading, currentImage, fullResolution, quality, pending, actions);
    container.append(section);
  });
}

function renderSource(source) {
  const container = document.querySelector("#source-information");
  container.replaceChildren();
  for (const [label, filename, pages] of [
    ["Exam", source.exam_pdf, source.exam_pages],
    ["Solutions", source.solutions_pdf, source.solutions_pages],
  ]) {
    const line = document.createElement("p");
    line.className = "source-line";
    line.textContent = `${label}: ${filename} · page${pages.length === 1 ? "" : "s"} ${pages.join(", ") || "not recorded"}`;
    container.append(line);
  }
}

function renderWarnings(warnings) {
  const list = document.querySelector("#importer-warnings");
  list.replaceChildren();
  (warnings.length ? warnings : ["No importer warnings."]).forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    list.append(item);
  });
}

function renderQualityWarnings(warnings) {
  const list = document.querySelector("#quality-warnings");
  list.replaceChildren();
  (warnings.length ? warnings : ["No automatic crop warnings."]).forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning.replaceAll("_", " ");
    list.append(item);
  });
}

function renderImageQuality(quality) {
  const details = document.createElement("p");
  details.className = "image-quality";
  if (!quality) {
    details.textContent = "No automatic quality metrics recorded.";
    return details;
  }
  const warningText = quality.warnings.length
    ? ` · warnings: ${quality.warnings.map((warning) => warning.replaceAll("_", " ")).join(", ")}`
    : " · no warnings";
  details.textContent =
    `${quality.pixel_width}×${quality.pixel_height}px · aspect ${quality.aspect_ratio}` +
    ` · whitespace ${Math.round(quality.whitespace_fraction * 100)}%${warningText}`;
  if (quality.warnings.length) details.classList.add("warning");
  return details;
}

function sourceImage(image, className) {
  const element = document.createElement("img");
  element.src = staticUrl(image.path);
  element.alt = image.alt_text;
  element.className = className;
  element.loading = "lazy";
  return element;
}

function staticUrl(path) {
  return `/static/${path.split("/").map(encodeURIComponent).join("/")}`;
}

async function uploadImage(problemId, slot, file) {
  if (!file) return;
  setMessage("Saving replacement…");
  const formData = new FormData();
  formData.append("image", file);
  const response = await fetch(
    `/api/manage/problems/${encodeURIComponent(problemId)}/images/${encodeURIComponent(slot)}/upload`,
    {method: "POST", headers: {"X-Management-Request": "1"}, body: formData},
  );
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || "Could not save the replacement.", "error");
    return;
  }
  await loadProblemList(problemId);
  setMessage(`${slot.replace(":", " ")} now uses the manual image.`, "success");
}

async function revertImage(problemId, slot) {
  const response = await fetch(
    `/api/manage/problems/${encodeURIComponent(problemId)}/images/${encodeURIComponent(slot)}`,
    {method: "DELETE", headers: {"X-Management-Request": "1"}},
  );
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || "Could not revert the image.", "error");
    return;
  }
  await loadProblemList(problemId);
  setMessage(`${slot.replace(":", " ")} restored to its generated image.`, "success");
}

async function setStatus(status) {
  const response = await fetch(`/api/manage/problems/${encodeURIComponent(currentProblemId)}/status`, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Management-Request": "1"},
    body: JSON.stringify({status}),
  });
  const data = await response.json();
  if (!response.ok) {
    setMessage(data.error || "Could not update the status.", "error");
    return;
  }
  await loadProblemList(currentProblemId);
  setMessage(`Image review status set to ${status.replace("_", " ")}.`, "success");
}

function updateNavigation() {
  const available = visibleProblems();
  const index = available.findIndex((problem) => problem.id === currentProblemId);
  previousButton.disabled = index <= 0;
  nextButton.disabled = index < 0 || index === available.length - 1;
}

function move(offset) {
  const available = visibleProblems();
  const index = available.findIndex((problem) => problem.id === currentProblemId);
  const next = available[index + offset];
  if (next) buildSelectors(next.id);
}

function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `manager-message ${type}`.trim();
}

statusFilter.addEventListener("change", () => buildSelectors(null));
yearSelect.addEventListener("change", () => {
  const available = visibleProblems();
  const selected = available.find((problem) => problem.year === Number(yearSelect.value));
  fillExamSelect(available, selected);
  fillProblemSelect(available, selected);
  loadProblem(problemSelect.value);
});
examSelect.addEventListener("change", () => {
  const available = visibleProblems();
  const selected = available.find(
    (problem) => problem.year === Number(yearSelect.value) && examKey(problem) === examSelect.value,
  );
  fillProblemSelect(available, selected);
  loadProblem(problemSelect.value);
});
problemSelect.addEventListener("change", () => loadProblem(problemSelect.value));
previousButton.addEventListener("click", () => move(-1));
nextButton.addEventListener("click", () => move(1));
document.querySelector("#mark-good").addEventListener("click", () => setStatus("looks_good"));
document.querySelector("#mark-bad").addEventListener("click", () => setStatus("bad_crop"));

loadProblemList().catch((error) => setMessage(error.message, "error"));
