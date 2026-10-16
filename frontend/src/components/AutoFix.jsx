import { useState } from "react";
import { fixFile, fixedUrl } from "../api.js";

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
      <section className="autofix">
        <h2>Автоисправление</h2>
        <p>Автоматически исправлять можно только файлы .docx. Для PDF загрузите исходный документ Word.</p>
      </section>
    );

  if (state.phase === "done") {
    const r = state.result;
    return (
      <section className="autofix">
        <h2>Готово: исправлено {r.total_applied}</h2>
        <p className="fix-summary">
          Замечаний: {r.issues_before} → {r.issues_after}
        </p>
        {r.applied.length > 0 && (
          <ul className="fix-list">
            {r.applied.map((a) => (
              <li key={a.name}>{a.name}<span>×{a.count}</span></li>
            ))}
          </ul>
        )}
        <a className="fix-download" href={fixedUrl(r.download_id)} download>⭳ Скачать исправленный файл</a>

        {r.remaining.length > 0 && (
          <div className="fix-remaining">
            <h3>Осталось исправить вручную</h3>
            <table>
              <tbody>
                {r.remaining.flatMap((c) =>
                  c.issues.map((i, idx) => (
                    <tr key={c.name + idx}>
                      <td className="loc">{i.location}</td>
                      <td>{i.message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        <p className="fix-warning">
          Исходный файл не изменён. Откройте исправленный документ в Word и просмотрите его: номера страниц
          и положение рисунков могли сдвинуться, а содержание нужно обновить (Ссылки → Обновить таблицу).
        </p>
      </section>
    );
  }

  return (
    <section className="autofix">
      <h2>Исправить автоматически</h2>
      <p>
        Сервис приведёт оформление к нормам: поля, шрифт, интервал, отступы, заголовки, подписи, нумерацию
        страниц. Смысл текста не меняется; то, что исправить нельзя, останется в списке.
      </p>
      <button className="submit-btn" onClick={run} disabled={state.phase === "loading"}>
        {state.phase === "loading" ? "Исправляем…" : "Исправить и скачать"}
      </button>
      {state.error && <div className="form-error" role="alert">{state.error}</div>}
    </section>
  );
}
