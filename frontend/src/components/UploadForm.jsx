import { useState } from "react";
import { Icon, attr } from "../ui.jsx";

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

  const message = error || serverError;
  return (
    <form
      className="upload"
      onSubmit={(e) => {
        e.preventDefault();
        if (file) onSubmit(file);
      }}
    >
      <label
        className={`dropzone${drag ? " drag" : ""}${file ? " has-file" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
      >
        <md-ripple />
        <span className="dz-icon"><Icon name={file ? "file" : "upload"} /></span>
        {file ? (
          <>
            <span className="title-medium dz-name">{file.name}</span>
            <span className="body-medium dz-hint">
              {(file.size / 1024 / 1024).toFixed(2)} МБ · нажмите, чтобы выбрать другой файл
            </span>
          </>
        ) : (
          <>
            <span className="title-medium">Перетащите файл сюда или нажмите</span>
            <span className="body-medium dz-hint">.docx или .pdf, до 20&nbsp;МБ</span>
          </>
        )}
        <input type="file" accept=".docx,.pdf" hidden onChange={(e) => pick(e.target.files[0])} />
      </label>

      {message && (
        <div className="banner banner-error body-medium" role="alert">
          <Icon name="error" /> {message}
        </div>
      )}

      <md-filled-button type="submit" disabled={attr(!file)} class="submit">
        <Icon name="check" slot="icon" />
        Проверить документ
      </md-filled-button>
    </form>
  );
}
