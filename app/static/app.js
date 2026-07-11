const intakeForm = document.querySelector("#intake-form");
const addJobButton = document.querySelector("#add-job");
const jobsContainer = document.querySelector("#jobs");
const livePreview = document.querySelector("#live-preview");

function jobTemplate(index) {
  return `
    <div class="job-tools">
      <strong>Experience ${index}</strong>
      <button class="button ghost remove-job" type="button">Remove</button>
    </div>
    <div class="grid two">
      <label>Employer<input name="employer"></label>
      <label>Job title<input name="job_title"></label>
      <label>Start date<input name="start_date"></label>
      <label>End date<input name="end_date"></label>
      <label class="wide">Bullet points<textarea name="bullets" rows="5"></textarea></label>
    </div>
  `;
}

function renumberJobs() {
  if (!jobsContainer) return;
  jobsContainer.querySelectorAll(".job-block").forEach((block, index) => {
    const title = block.querySelector(".job-tools strong");
    if (title) title.textContent = `Experience ${index + 1}`;
  });
}

function debounce(callback, wait = 250) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), wait);
  };
}

async function refreshPreview() {
  if (!intakeForm || !livePreview) return;
  const response = await fetch("/preview/live", {
    method: "POST",
    body: new FormData(intakeForm),
  });
  if (response.ok) {
    livePreview.srcdoc = await response.text();
  }
}

const debouncedRefreshPreview = debounce(refreshPreview);

if (addJobButton && jobsContainer) {
  addJobButton.addEventListener("click", () => {
    const block = document.createElement("div");
    block.className = "job-block";
    block.innerHTML = jobTemplate(jobsContainer.querySelectorAll(".job-block").length + 1);
    jobsContainer.appendChild(block);
    renumberJobs();
    refreshPreview();
  });

  jobsContainer.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains("remove-job")) return;
    const blocks = jobsContainer.querySelectorAll(".job-block");
    if (blocks.length === 1) {
      target.closest(".job-block").querySelectorAll("input, textarea").forEach((field) => {
        field.value = "";
      });
    } else {
      target.closest(".job-block").remove();
    }
    renumberJobs();
    refreshPreview();
  });
}

if (intakeForm) {
  intakeForm.addEventListener("input", debouncedRefreshPreview);
  intakeForm.addEventListener("change", refreshPreview);
}
