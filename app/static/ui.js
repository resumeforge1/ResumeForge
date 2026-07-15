document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const csrf = document.cookie
    .split("; ")
    .find((part) => part.startsWith("rf_csrf="))
    ?.split("=")[1];
  if (csrf && form.method.toLowerCase() === "post" && !form.querySelector("input[name='_csrf']")) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "_csrf";
    input.value = decodeURIComponent(csrf);
    form.appendChild(input);
  }
  const button = form.querySelector("button[type='submit']");
  if (!button || button.dataset.noLoading === "true") return;
  button.disabled = true;
  const label = button.textContent || "Working";
  button.dataset.originalLabel = label;
  button.innerHTML = `<span class="loading-spinner" aria-hidden="true"></span><span>${label}</span>`;
});

document.querySelectorAll("details[data-persist]").forEach((details) => {
  const key = `rf:${details.dataset.persist}`;
  const saved = window.localStorage.getItem(key);
  if (saved === "closed") details.removeAttribute("open");
  if (saved === "open") details.setAttribute("open", "");
  details.addEventListener("toggle", () => {
    window.localStorage.setItem(key, details.open ? "open" : "closed");
  });
});
