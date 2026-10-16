import { useState } from "react";

const OK_EXT = /\.(docx|pdf)$/i;

export default function UploadForm({ onSubmit, serverError }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);

  function pick(f) {
    if (!f) return;
    if (!OK_EXT.test(f.name)) {
      setFile(null);
      setError("Поддерживаются только файлы .docx и .pdf.");
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setFile(null);
      setError("Файл слишком большой (максимум 20 МБ).");
      return;
    }
    setError(null);
    setFile(f);
  }

  return (
    <form
      className="upload"
      onSubmit={(e) => {
        e.preventDefault();
        if (file) onSubmit(file);
      }}
    >
      <label
        className={`dropzone${drag ? " drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
      >
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 3v12m0-12l-4 4m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
        </svg>
        <span className="dz-main">Перетащите файл сюда или нажмите</span>
        <span className="dz-hint">.docx или .pdf, до 20&nbsp;МБ</span>
        <input type="file" accept=".docx,.pdf" hidden onChange={(e) => pick(e.target.files[0])} />
      </label>
      {file && <div className="filename">{file.name}</div>}
      <button type="submit" className="submit-btn" disabled={!file}>Проверить документ</button>
      {(error || serverError) && <div className="form-error" role="alert">{error || serverError}</div>}
    </form>
  );
}
