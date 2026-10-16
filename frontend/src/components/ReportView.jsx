import { useState } from "react";
import { reportUrl } from "../api.js";
import { Icon } from "../ui.jsx";

const PAGE = 30;

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

function Category({ cat }) {
  const [shown, setShown] = useState(PAGE);
  return (
    <details className="accordion" open>
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

function plural(n) {
  if (n % 10 === 1 && n % 100 !== 11) return "замечание";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "замечания";
  return "замечаний";
}

export default function ReportView({ report }) {
  const { clean, total, categories, notes } = report;
  return (
    <div className="report">
      <div className={`summary ${clean ? "summary-ok" : "summary-bad"}`}>
        <span className="summary-icon"><Icon name={clean ? "ok" : "report"} /></span>
        <div className="summary-text">
          <div className="headline-small">{clean ? "Соответствует нормам" : `${total} ${plural(total)}`}</div>
          <div className="body-medium">{report.file} · {report.profile.title} · {report.checked_at}</div>
        </div>
        <md-outlined-button href={reportUrl(report.report_id)} download="">
          <Icon name="download" slot="icon" />
          Отчёт .html
        </md-outlined-button>
      </div>

      {notes.length > 0 && (
        <ul className="notes body-medium">
          {notes.map((n) => <li key={n}><Icon name="info" /> {n}</li>)}
        </ul>
      )}

      {clean
        ? <p className="body-large clean-msg">Замечаний не обнаружено. Документ соответствует заданным нормам.</p>
        : categories.map((c) => <Category key={c.name} cat={c} />)}
    </div>
  );
}
