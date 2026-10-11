(function () {
  "use strict";

  const STORAGE_KEY = "fmaTrainer.progress";
  const SCHEMA_VERSION = 1;

  function cleanProgress() {
    return {
      schemaVersion: SCHEMA_VERSION,
      problems: Object.create(null),
    };
  }

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function isNonNegativeInteger(value) {
    return Number.isInteger(value) && value >= 0;
  }

  function isValidProblemRecord(record) {
    return (
      isObject(record) &&
      isNonNegativeInteger(record.attempts) &&
      isNonNegativeInteger(record.correct) &&
      isNonNegativeInteger(record.incorrect) &&
      record.attempts === record.correct + record.incorrect &&
      typeof record.lastCorrect === "boolean" &&
      typeof record.lastAttemptedAt === "string" &&
      record.lastAttemptedAt.length > 0 &&
      !Number.isNaN(Date.parse(record.lastAttemptedAt))
    );
  }

  function validateProgress(value) {
    if (
      !isObject(value) ||
      value.schemaVersion !== SCHEMA_VERSION ||
      !isObject(value.problems)
    ) {
      return cleanProgress();
    }

    const progress = cleanProgress();
    for (const [problemId, record] of Object.entries(value.problems)) {
      if (problemId && isValidProblemRecord(record)) {
        progress.problems[problemId] = {
          attempts: record.attempts,
          correct: record.correct,
          incorrect: record.incorrect,
          lastCorrect: record.lastCorrect,
          lastAttemptedAt: record.lastAttemptedAt,
        };
      }
    }
    return progress;
  }

  function getStorage() {
    try {
      return window.localStorage;
    } catch (_error) {
      return null;
    }
  }

  function readStoredProgress(storage) {
    let storedValue;
    try {
      storedValue = storage.getItem(STORAGE_KEY);
    } catch (_error) {
      return { progress: cleanProgress(), canSave: false };
    }

    if (storedValue === null) {
      return { progress: cleanProgress(), canSave: true };
    }

    try {
      return {
        progress: validateProgress(JSON.parse(storedValue)),
        canSave: true,
      };
    } catch (_error) {
      return { progress: cleanProgress(), canSave: true };
    }
  }

  function getProgress() {
    const storage = getStorage();
    return storage
      ? readStoredProgress(storage).progress
      : cleanProgress();
  }

  function recordAttempt(problemId, wasCorrect) {
    if (
      !problemId ||
      typeof problemId !== "string" ||
      typeof wasCorrect !== "boolean"
    ) {
      return false;
    }

    const storage = getStorage();
    if (!storage) {
      return false;
    }

    const storedProgress = readStoredProgress(storage);
    if (!storedProgress.canSave) {
      return false;
    }

    const progress = storedProgress.progress;
    const previous = progress.problems[problemId] || {
      attempts: 0,
      correct: 0,
      incorrect: 0,
    };

    progress.problems[problemId] = {
      attempts: previous.attempts + 1,
      correct: previous.correct + (wasCorrect ? 1 : 0),
      incorrect: previous.incorrect + (wasCorrect ? 0 : 1),
      lastCorrect: wasCorrect,
      lastAttemptedAt: new Date().toISOString(),
    };

    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(progress));
      return true;
    } catch (_error) {
      return false;
    }
  }

  function clearProgress() {
    const storage = getStorage();
    if (!storage) {
      return false;
    }

    try {
      storage.removeItem(STORAGE_KEY);
      return true;
    } catch (_error) {
      return false;
    }
  }

  window.FmaProgress = Object.freeze({
    clearProgress,
    getProgress,
    recordAttempt,
  });
})();
