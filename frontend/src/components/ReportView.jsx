import { useEffect, useState } from "react";
import { annotatedUrl, reportUrl } from "../api.js";
import { Icon } from "../ui.jsx";

const PAGE = 30;
const COLLAPSE_OVER = 20; // при большом числе замечаний разделы свёрнуты, обзор — в чипах

export function IssueList({ issues }) {
  return (
    <ul className="issue-list">
      {issues.map((i, idx) => (
        <li key={idx}>
          <span className="issue-msg body-medium">{i.message}</span>
          <span className="issue-loc label-medium">{i.location}</span>
        </li>
      ))}
    </ul>
  );
}

function Category({ cat, id, open, onToggle }) {
  const [shown, setShown] = useState(PAGE);
  return (
    <details
      className="accordion"
      id={id}
      open={open}
      onToggle={(e) => onToggle(e.currentTarget.open)}
    >
      <summary className="title-medium">
        <span>{cat.name}</span>
        <span className="badge label-medium">{cat.count}</span>
        <span className="chevron"><Icon name="chevron" /></span>
      </summary>
      <IssueList issues={cat.issues.slice(0, shown)} />
      {shown < cat.count && (
        <md-text-button onClick={() => setShown(shown + 100)} class="more">
          Показать ещё ({cat.count - shown})
        </md-text-button>
      )}
    </details>
  );
}

export function plural(n) {
  if (n % 10 === 1 && n % 100 !== 11) return "замечание";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "замечания";
  return "замечаний";
}

/** children — блок действий (автоисправление), показывается сразу под сводкой, до списка замечаний. */
export default function ReportView({ report, children }) {
  const { clean, total, categories, notes } = report;
  const [open, setOpen] = useState(() => categories.map(() => total <= COLLAPSE_OVER));

  const [scrollTo, setScrollTo] = useState(null);

  // прокрутка к разделу — после того, как он раскрылся и страница перерисовалась
  useEffect(() => {
    if (scrollTo === null) return;
    document.getElementById(`cat-${scrollTo.idx}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [scrollTo]);

  function reveal(idx) {
    setOpen((o) => o.map((v, i) => (i === idx ? true : v)));
    setScrollTo({ idx }); // новый объект — повторный клик по тому же чипу тоже прокрутит
  }

  return (
    <div className="report">
      <div className="summary">
        <span className={`summary-icon ${clean ? "ok" : "bad"}`}><Icon name={clean ? "ok" : "report"} /></span>
        <div className="summary-text">
          <h1 className="headline-small">{clean ? "Соответствует нормам" : `${total} ${plural(total)}`}</h1>
          <div className="title-medium summary-file">{report.file}</div>
          <div className="body-medium summary-meta">{report.profile.title} · проверено {report.checked_at}</div>
          {!clean && (
            <ul className="overview">
              {categories.map((c, idx) => (
                <li key={c.name}>
                  <button type="button" className="chip label-large" onClick={() => reveal(idx)}>
                    {c.name}<b>{c.count}</b>
                    <md-ripple />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="summary-actions">
          {report.upload_id && !clean ? (
            <>
              {/* .docx: сама работа с подсветкой и примечаниями Word на местах ошибок */}
              <md-filled-tonal-button href={annotatedUrl(report.upload_id, report.profile.key, report.standards)} download="">
                <Icon name="file" slot="icon" />
                Работа с отметками
              </md-filled-tonal-button>
              <md-text-button href={reportUrl(report.report_id)} download="">
                <Icon name="download" slot="icon" />
                Отчёт .html
              </md-text-button>
            </>
          ) : (
            <md-outlined-button href={reportUrl(report.report_id)} download="">
              <Icon name="download" slot="icon" />
              Скачать отчёт
            </md-outlined-button>
          )}
        </div>
      </div>

      {notes.length > 0 && (
        <ul className="notes body-medium">
          {notes.map((n) => <li key={n}><Icon name="info" /><span>{n}</span></li>)}
        </ul>
      )}

      {children}

      {!clean && (
        <>
          <h2 className="title-large section-title">Замечания</h2>
          {categories.map((c, idx) => (
            <Category
              key={c.name}
              id={`cat-${idx}`}
              cat={c}
              open={open[idx]}
              onToggle={(v) => setOpen((o) => (o[idx] === v ? o : o.map((x, i) => (i === idx ? v : x))))}
            />
          ))}
        </>
      )}
    </div>
  );
}
