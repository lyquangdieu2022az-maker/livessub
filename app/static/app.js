const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#file");
const sourceLanguageInput = document.querySelector("#source_language");
const submitButton = document.querySelector("#submit-button");
const video = document.querySelector("#video");
const playerStage = document.querySelector("#player-stage");
const emptyState = document.querySelector("#empty-state");
const subtitleOverlay = document.querySelector("#subtitle-overlay");
const statusCard = document.querySelector("#status-card");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const statusError = document.querySelector("#status-error");
const progressBar = document.querySelector("#progress-bar");
const progressPill = document.querySelector("#progress-pill");
const segmentCount = document.querySelector("#segment-count");
const detectedLanguage = document.querySelector("#detected-language");
const cleanupStatus = document.querySelector("#cleanup-status");
const downloadList = document.querySelector("#download-list");

let activeJobId = null;
let currentJobStatus = "idle";
let pollingTimer = null;
let selectedFile = null;
let currentObjectUrl = null;
let subtitleSegments = [];
let nextSegmentIndex = 0;
let overlayFrame = null;
let isSubmitting = false;

fileInput.addEventListener("change", async () => {
  prepareSelectedFile();
  if (selectedFile) {
    await startJob();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await startJob();
});

video.addEventListener("play", startOverlayLoop);
video.addEventListener("pause", stopOverlayLoop);
video.addEventListener("ended", stopOverlayLoop);
video.addEventListener("seeked", renderCurrentSubtitle);
video.addEventListener("timeupdate", renderCurrentSubtitle);

function prepareSelectedFile() {
  selectedFile = fileInput.files?.[0] || null;
  resetJobState();

  if (!selectedFile) {
    resetPlayer();
    return;
  }

  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
  }

  currentObjectUrl = URL.createObjectURL(selectedFile);
  video.src = currentObjectUrl;
  video.load();

  playerStage.classList.remove("is-empty");
  emptyState.classList.add("hidden");
  submitButton.disabled = false;
  submitButton.textContent = "Dich lai video nay";

  statusCard.classList.remove("hidden");
  statusTitle.textContent = selectedFile.name;
  statusMessage.textContent =
    "Video dang san sang trong player. App se bat dau tao phu de tieng Viet ngay.";
  updateProgress(2);
  updateOverlay("Dang tai video len de tao subtitle tieng Viet...", true);
}

async function startJob() {
  if (!selectedFile || isSubmitting) {
    return;
  }

  isSubmitting = true;
  submitButton.disabled = true;
  submitButton.textContent = "Dang tao phu de...";
  statusError.classList.add("hidden");
  downloadList.innerHTML = "";
  subtitleSegments = [];
  nextSegmentIndex = 0;
  segmentCount.textContent = "0";
  detectedLanguage.textContent = "Dang doan";
  cleanupStatus.textContent = "Dang cho";
  currentJobStatus = "queued";
  updateProgress(6);
  updateOverlay("Dang tao nhung cau phu de dau tien...", true);

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("target_language", "Vietnamese");
  formData.append("source_language", sourceLanguageInput.value.trim());
  formData.append("translate", "true");

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Khong the tao job.");
    }

    activeJobId = payload.job_id;
    statusTitle.textContent = selectedFile.name;
    statusMessage.textContent = payload.message;
    startPolling();
  } catch (error) {
    showError(error.message || "Da xay ra loi khi gui video.");
    submitButton.disabled = false;
    submitButton.textContent = "Thu lai";
    currentJobStatus = "failed";
    updateOverlay("Khong tao duoc phu de cho video nay.", true);
  } finally {
    isSubmitting = false;
  }
}

function startPolling() {
  stopPolling();
  pollOnce();
  pollingTimer = setInterval(pollOnce, 1500);
}

function stopPolling() {
  if (!pollingTimer) {
    return;
  }
  clearInterval(pollingTimer);
  pollingTimer = null;
}

async function pollOnce() {
  if (!activeJobId) {
    return;
  }

  try {
    const response = await fetch(`/api/jobs/${activeJobId}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Khong doc duoc trang thai job.");
    }

    currentJobStatus = payload.status;
    renderStatus(payload);
    await fetchNewSegments();

    if (payload.status === "completed" || payload.status === "failed") {
      stopPolling();
      submitButton.disabled = false;
      submitButton.textContent = "Dich lai video nay";
      renderCurrentSubtitle();
    }
  } catch (error) {
    stopPolling();
    showError(error.message || "Mat ket noi voi server.");
    submitButton.disabled = false;
    submitButton.textContent = "Thu lai";
  }
}

async function fetchNewSegments() {
  if (!activeJobId) {
    return;
  }

  const response = await fetch(
    `/api/jobs/${activeJobId}/segments?from_index=${nextSegmentIndex}`
  );
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || "Khong lay duoc subtitle.");
  }

  if (payload.segments?.length) {
    subtitleSegments.push(...payload.segments);
    nextSegmentIndex = payload.next_index;
    segmentCount.textContent = String(nextSegmentIndex);
    renderCurrentSubtitle();
  }
}

function renderStatus(job) {
  const label = {
    queued: "Da nhan video",
    processing: "Dang dich live",
    completed: "Hoan tat",
    failed: "That bai",
  }[job.status] || "Dang xu ly";

  statusTitle.textContent = `${label}: ${job.filename}`;
  statusMessage.textContent = job.message || "";
  detectedLanguage.textContent = job.detected_language || "Dang doan";
  cleanupStatus.textContent = job.media_deleted ? "Da xoa video tam" : "Dang giu tam";
  segmentCount.textContent = String(job.translated_segment_count || subtitleSegments.length);
  updateProgress(job.progress || 0);

  if (job.status === "failed" && job.error) {
    showError(job.error);
  } else {
    statusError.classList.add("hidden");
  }

  renderDownloads(job.outputs || {});
}

function renderDownloads(outputs) {
  const entries = [
    ["Transcript goc .srt", outputs.original_srt],
    ["Transcript goc .vtt", outputs.original_vtt],
    ["Subtitle tieng Viet .srt", outputs.translated_srt],
    ["Subtitle tieng Viet .vtt", outputs.translated_vtt],
    ["Transcript JSON", outputs.transcript_json],
  ].filter(([, filename]) => Boolean(filename));

  downloadList.innerHTML = "";

  for (const [label, filename] of entries) {
    const wrapper = document.createElement("div");
    wrapper.className = "download-item";

    const text = document.createElement("span");
    text.textContent = label;

    const link = document.createElement("a");
    link.href = `/download/${activeJobId}/${filename}`;
    link.textContent = "Tai xuong";
    link.target = "_blank";
    link.rel = "noreferrer";

    wrapper.append(text, link);
    downloadList.appendChild(wrapper);
  }
}

function startOverlayLoop() {
  stopOverlayLoop();

  const tick = () => {
    renderCurrentSubtitle();
    if (!video.paused && !video.ended) {
      overlayFrame = requestAnimationFrame(tick);
    }
  };

  overlayFrame = requestAnimationFrame(tick);
}

function stopOverlayLoop() {
  if (!overlayFrame) {
    return;
  }
  cancelAnimationFrame(overlayFrame);
  overlayFrame = null;
}

function renderCurrentSubtitle() {
  if (!selectedFile) {
    updateOverlay("Chon video de bat dau.", true);
    return;
  }

  const currentTime = Number.isFinite(video.currentTime) ? video.currentTime : 0;
  const activeIndex = findSegmentIndex(currentTime);

  if (activeIndex >= 0) {
    updateOverlay(subtitleSegments[activeIndex].text, false);
    return;
  }

  if (!subtitleSegments.length && activeJobId) {
    updateOverlay("Dang tao nhung cau subtitle dau tien...", true);
    return;
  }

  const lastSegment = subtitleSegments[subtitleSegments.length - 1];
  if (
    activeJobId &&
    (currentJobStatus === "queued" || currentJobStatus === "processing") &&
    (!lastSegment || currentTime > lastSegment.end)
  ) {
    updateOverlay("Dang dich tiep de bat kip video...", true);
    return;
  }

  updateOverlay("", false);
}

function findSegmentIndex(time) {
  let low = 0;
  let high = subtitleSegments.length - 1;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const segment = subtitleSegments[mid];

    if (time < segment.start) {
      high = mid - 1;
    } else if (time > segment.end) {
      low = mid + 1;
    } else {
      return mid;
    }
  }

  return -1;
}

function updateProgress(value) {
  progressBar.style.width = `${value}%`;
  progressPill.textContent = `${value}%`;
}

function updateOverlay(text, isPlaceholder) {
  subtitleOverlay.textContent = text;
  subtitleOverlay.classList.toggle("is-placeholder", Boolean(isPlaceholder));
}

function showError(message) {
  statusError.textContent = message;
  statusError.classList.remove("hidden");
}

function resetJobState() {
  stopPolling();
  activeJobId = null;
  currentJobStatus = "idle";
  subtitleSegments = [];
  nextSegmentIndex = 0;
  segmentCount.textContent = "0";
  detectedLanguage.textContent = "Dang cho";
  cleanupStatus.textContent = "Dang cho";
  downloadList.innerHTML = "";
  statusError.classList.add("hidden");
}

function resetPlayer() {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }

  selectedFile = null;
  video.removeAttribute("src");
  video.load();
  playerStage.classList.add("is-empty");
  emptyState.classList.remove("hidden");
  submitButton.disabled = true;
  submitButton.textContent = "Bat dich tieng Viet";
  updateOverlay("Chon video de bat dau.", true);
  updateProgress(0);
}
