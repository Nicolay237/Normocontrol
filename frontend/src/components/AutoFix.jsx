import { useState } from "react";
import { fixFile, fixedUrl } from "../api.js";
import { Icon, attr } from "../ui.jsx";
import { IssueList } from "./ReportView.jsx";

/** Карточка: иконка слева, весь контент — в одной колонке справа от неё. */
function Card({ icon, done, children }) {
  return (
    <section className="autofix">
      <div className="autofix-head">
        <span className={`autofix-icon${done ? " done" : ""}`}><Icon name={icon} /></span>
        <div className="autofix-body">{children}</div>
      </div>
    </section>
  );
}

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
      <Card icon="fix">
        <h2 className="title-large">Автоисправление недоступно для PDF</h2>
        <p className="body-medium">Загрузите исходный документ Word (.docx) — его можно исправить автоматически.</p>
      </Card>
    );

  if (state.phase === "done") {
    const r = state.result;
    const remaining = r.remaining.flatMap((c) => c.issues);
    return (
      <Card icon="ok" done>
        <h2 className="title-large">Исправлено: {r.total_applied}</h2>
        <p className="body-medium">
          Замечаний было {r.issues_before}, осталось {r.issues_after}. Исходный файл не изменён.
        </p>

        <md-filled-button href={fixedUrl(r.download_id)} download="">
          <Icon name="download" slot="icon" />
          Скачать исправленный файл
        </md-filled-button>

        {r.applied.length > 0 && (
          <details className="fix-details">
            <summary className="label-large">
              Что изменено <span className="chevron"><Icon name="chevron" size={20} /></span>
            </summary>
            <ul className="applied-list">
              {r.applied.map((a) => (
                <li key={a.name} className="body-medium">
                  <Icon name="tick" size={18} />
                  <span>{a.name}</span>
                  <b className="label-medium">×{a.count}</b>
                </li>
              ))}
            </ul>
          </details>
        )}

        {remaining.length > 0 && (
          <div className="remaining">
            <h3 className="title-medium">Осталось исправить вручную</h3>
            <IssueList issues={remaining} />
          </div>
        )}

        <p className="body-medium note">
          <Icon name="info" />
          <span>
            Откройте исправленный документ в Word и просмотрите его: страницы и рисунки могли сдвинуться,
            а содержание нужно обновить (Ссылки → Обновить таблицу).
          </span>
        </p>
      </Card>
    );
  }

  const loading = state.phase === "loading";
  return (
    <Card icon="fix">
      <h2 className="title-large">Исправить автоматически</h2>
      <p className="body-medium">
        Поля, шрифт, интервал, отступы, заголовки, подписи и нумерация страниц будут приведены к нормам.
        Текст работы не меняется, то, что нельзя исправить, останется в списке.
      </p>
      {loading && <md-linear-progress indeterminate="" class="progress" />}
      <md-filled-button onClick={run} disabled={attr(loading)}>
        <Icon name="fix" slot="icon" />
        {loading ? "Исправляем… обычно до полуминуты" : "Исправить и скачать"}
      </md-filled-button>
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
      )}
    </Card>
  );
}
