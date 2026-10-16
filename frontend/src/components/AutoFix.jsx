import { useState } from "react";
import { fixFile, fixedUrl } from "../api.js";
import { Icon, attr } from "../ui.jsx";
import { IssueList } from "./ReportView.jsx";

export default function AutoFix({ file, profileKey }) {
  const [state, setState] = useState({ phase: "idle", result: null, error: null });
  const isDocx = /\.docx$/i.test(file?.name ?? "");

  async function run() {
    setState({ phase: "loading", result: null, error: null });
    try {
      const result = await fixFile(file, profileKey);
      setState({ phase: "done", result, error: null });
    } catch (e) {
      setState({ phase: "idle", result: null, error: e.message });
    }
  }

  if (!isDocx)
    return (
      <section className="card card-tonal autofix">
        <h2 className="title-large">Автоисправление</h2>
        <p className="body-medium">Автоматически исправлять можно только файлы .docx. Для PDF загрузите исходный документ Word.</p>
      </section>
    );

  if (state.phase === "done") {
    const r = state.result;
    const remaining = r.remaining.flatMap((c) => c.issues);
    return (
      <section className="card card-tonal autofix">
        <h2 className="title-large">Готово: исправлено {r.total_applied}</h2>
        <p className="body-large">Замечаний: {r.issues_before} → {r.issues_after}</p>

        {r.applied.length > 0 && (
          <ul className="chip-set">
            {r.applied.map((a) => (
              <li key={a.name} className="chip label-large">{a.name}<b>×{a.count}</b></li>
            ))}
          </ul>
        )}

        <md-filled-button href={fixedUrl(r.download_id)} download="">
          <span slot="icon" className="material-symbols-outlined">download</span>
          Скачать исправленный файл
        </md-filled-button>

        {remaining.length > 0 && (
          <div className="remaining">
            <h3 className="title-medium">Осталось исправить вручную</h3>
            <IssueList issues={remaining} />
          </div>
        )}
        <p className="body-medium note">
          <Icon name="info" />
          <span>
            Исходный файл не изменён. Откройте исправленный документ в Word и просмотрите его:
            номера страниц и положение рисунков могли сдвинуться, а содержание нужно обновить (Ссылки → Обновить таблицу).
          </span>
        </p>
      </section>
    );
  }

  return (
    <section className="card card-tonal autofix">
      <h2 className="title-large">Исправить автоматически</h2>
      <p className="body-medium">
        Сервис приведёт оформление к нормам: поля, шрифт, интервал, отступы, заголовки, подписи, нумерацию
        страниц. Смысл текста не меняется; то, что исправить нельзя, останется в списке.
      </p>
      {state.phase === "loading" && <md-linear-progress indeterminate="" class="progress" />}
      <md-filled-button onClick={run} disabled={attr(state.phase === "loading")}>
        <span slot="icon" className="material-symbols-outlined">auto_fix_high</span>
        {state.phase === "loading" ? "Исправляем…" : "Исправить и скачать"}
      </md-filled-button>
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /> {state.error}</div>
      )}
    </section>
  );
}
