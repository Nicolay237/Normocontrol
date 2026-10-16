import { useState } from "react";
import { reportUrl } from "../api.js";

const PAGE = 30;

function Category({ cat }) {
  const [shown, setShown] = useState(PAGE);
  const items = cat.issues.slice(0, shown);
  return (
    <details className="category" open>
      <summary>
        <span>{cat.name}</span>
        <span className="cat-count">{cat.count}</span>
      </summary>
      <table>
        <tbody>
          {items.map((i, idx) => (
            <tr key={idx}>
              <td className="loc">{i.location}</td>
              <td>{i.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown < cat.count && (
        <button className="more-btn" onClick={() => setShown(shown + 100)}>
          Показать ещё ({cat.count - shown})
        </button>
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
    <div className="report-card">
      <div className="download-bar">
        <a href={reportUrl(report.report_id)} download>⭳ Скачать отчёт для студента</a>
      </div>
      <header>
        <div>
          <h1>Отчёт нормоконтроля</h1>
          <div className="meta">{report.file} · {report.profile.title} · {report.checked_at}</div>
        </div>
        <div className={`stamp ${clean ? "stamp-ok" : "stamp-bad"}`}>
          {clean ? "СООТВЕТСТВУЕТ НОРМАМ" : `${total} ${plural(total)}`.toUpperCase()}
        </div>
      </header>
      <hr />
      {notes.length > 0 && <ul className="notes">{notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      {clean ? (
        <p className="clean-msg">Замечаний не обнаружено. Документ соответствует заданным нормам.</p>
      ) : (
        categories.map((c) => <Category key={c.name} cat={c} />)
      )}
      <footer>Нормы: ГОСТ 7.32-2017 · {report.profile.title}</footer>
    </div>
  );
}
