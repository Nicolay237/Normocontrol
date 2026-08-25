(() => {
  const form = document.getElementById("upload-form");
  const dropzone = document.getElementById("dropzone");
  const input = document.getElementById("file");
  const submitBtn = document.getElementById("submit-btn");
  const filenameBox = document.getElementById("filename");
  const errorBox = document.getElementById("form-error");
  const hero = document.querySelector(".hero");
  const features = document.getElementById("features");
  const loading = document.getElementById("loading");
  const resultsSection = document.getElementById("results-section");
  const results = document.getElementById("results");
  const resetBtn = document.getElementById("reset-btn");

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function setFile(file) {
    if (!file) return;
    const okExt = /\.(docx|pdf)$/i.test(file.name);
    if (!okExt) {
      showError("Поддерживаются только файлы .docx и .pdf.");
      input.value = "";
      submitBtn.disabled = true;
      filenameBox.hidden = true;
      return;
    }
    clearError();
    filenameBox.textContent = file.name;
    filenameBox.hidden = false;
    submitBtn.disabled = false;
  }

  input.addEventListener("change", () => setFile(input.files[0]));

  ["dragover", "dragleave", "drop"].forEach((evName) => {
    dropzone.addEventListener(evName, (e) => {
      e.preventDefault();
      dropzone.classList.toggle("drag", evName === "dragover");
    });
  });
  dropzone.addEventListener("drop", (e) => {
    input.files = e.dataTransfer.files;
    setFile(input.files[0]);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = input.files[0];
    if (!file) return;
    clearError();

    hero.hidden = true;
    features.hidden = true;
    loading.hidden = false;

    const data = new FormData();
    data.append("file", file);

    try {
      const resp = await fetch("/api/check", { method: "POST", body: data });
      if (!resp.ok) {
        const problem = await resp.json().catch(() => ({}));
        throw new Error(problem.error || "Не удалось проверить документ. Попробуйте ещё раз.");
      }
      const html = await resp.text();
      results.innerHTML = html;
      resultsSection.hidden = false;
      loading.hidden = true;
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      loading.hidden = true;
      hero.hidden = false;
      features.hidden = false;
      showError(err.message || "Произошла ошибка. Попробуйте ещё раз.");
    }
  });

  resetBtn.addEventListener("click", () => {
    resultsSection.hidden = true;
    results.innerHTML = "";
    hero.hidden = false;
    features.hidden = false;
    input.value = "";
    filenameBox.hidden = true;
    submitBtn.disabled = true;
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
})();
