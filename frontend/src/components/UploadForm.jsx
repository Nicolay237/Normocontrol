import { useState } from "react";
import { Icon, attr } from "../ui.jsx";

const OK_EXT = /\.(docx|pdf)$/i;
const DOCX_EXT = /\.docx$/i;

/** docxOnly — только Word (оформление статьи); submitLabel — надпись на кнопке. */
export default function UploadForm({ onSubmit, serverError, docxOnly = false, submitLabel = "Проверить документ" }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);

  function pick(f) {
    if (!f) return;
    if (!(docxOnly ? DOCX_EXT : OK_EXT).test(f.name)) {
      setFile(null);
      setError(docxOnly ? "Загрузите файл Word (.docx)." : "Поддерживаются только файлы .docx и .pdf.");
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
              {(file.size / 1024 / 1024).toFixed(2).replace(".", ",")} МБ · нажмите, чтобы выбрать другой файл
            </span>
          </>
        ) : (
          <>
            <span className="title-medium">Перетащите файл сюда</span>
            <span className="body-medium dz-hint">
              или <span className="dz-link">выберите на компьютере</span>
            </span>
            <span className="dz-formats label-medium">
              <span>DOCX</span>{!docxOnly && <span>PDF</span>}<span>до 20&nbsp;МБ</span>
            </span>
          </>
        )}
        <input type="file" accept={docxOnly ? ".docx" : ".docx,.pdf"} className="visually-hidden" onChange={(e) => pick(e.target.files[0])} />
      </label>

      {message && (
        <div className="banner banner-error body-medium" role="alert">
          <Icon name="error" /><span>{message}</span>
        </div>
      )}

      <md-filled-button type="submit" disabled={attr(!file)} class="submit">
        <Icon name="check" slot="icon" />
        {file ? submitLabel : "Выберите файл, чтобы начать"}
      </md-filled-button>
    </form>
  );
}
