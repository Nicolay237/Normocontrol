import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../ui.jsx";
import { IssueList, plural } from "./ReportView.jsx";
import { Rich } from "../pages/LegalPage.jsx";
import home from "../../../content/home.json"; // настоящий отчёт по курсовой с ошибками (scripts/make_home_example.py)

const FIRST = 4; // сколько разделов видно сразу — остальные по кнопке или по чипу

/**
 * Пример отчёта на главной: посетитель видит результат проверки, ещё не загрузив свою работу.
 * Та же разметка, что у настоящего отчёта (ReportView), но без скачивания файлов.
 */
export default function ExampleReport() {
  const ex = home.example;
  const cats = ex.categories;
  const [open, setOpen] = useState(() => cats.map((_, i) => i < 2));
  const [all, setAll] = useState(false);
  const [scrollTo, setScrollTo] = useState(null);

  useEffect(() => {
    if (scrollTo === null) return;
    document.getElementById(`ex-cat-${scrollTo.idx}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [scrollTo]);

  function reveal(idx) {
    setAll(true);
    setOpen((o) => o.map((v, i) => (i === idx ? true : v)));
    setScrollTo({ idx });
  }

  const shown = all ? cats : cats.slice(0, FIRST);
  return (
    <section className="example" aria-labelledby="example-title">
      <h2 id="example-title" className="headline-small">Как выглядит отчёт</h2>
      <p className="body-large supporting supporting-wide">
        Это настоящий отчёт сервиса по курсовой с типичными ошибками. У каждого замечания — где оно
        (страница, абзац, начало текста) и что ожидается по ГОСТ. Для .docx вы также получаете копию работы
        с отметками на местах ошибок.
      </p>

      <div className="example-frame report">
        <span className="tag example-tag label-medium">Пример</span>
        <div className="summary">
          <span className="summary-icon bad"><Icon name="report" /></span>
          <div className="summary-text">
            <h3 className="headline-small">{ex.total} {plural(ex.total)}</h3>
            <div className="title-medium summary-file">{ex.file}</div>
            <div className="body-medium summary-meta">{ex.profile} · пример проверки</div>
            <ul className="overview">
              {cats.map((c, idx) => (
                <li key={c.name}>
                  <button type="button" className="chip label-large" onClick={() => reveal(idx)}>
                    {c.name}<b>{c.count}</b>
                    <md-ripple />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="example-fix body-medium">
          <span className="summary-icon ok"><Icon name="fix" /></span>
          <span>
            <b>Автоисправление</b> убрало из этой работы {ex.total - ex.after_fix} {plural(ex.total - ex.after_fix)} из{" "}
            {ex.total} — осталось {ex.after_fix}, их отчёт перечисляет для ручной правки.
          </span>
        </div>

        {shown.map((c) => {
          const idx = cats.indexOf(c);
          return (
            <details key={c.name} className="accordion" id={`ex-cat-${idx}`} open={open[idx]}
                     onToggle={(e) => { const v = e.currentTarget.open; setOpen((o) => (o[idx] === v ? o : o.map((x, i) => (i === idx ? v : x)))); }}>
              <summary className="title-medium">
                <span>{c.name}</span>
                <span className="badge label-medium">{c.count}</span>
                <span className="chevron"><Icon name="chevron" /></span>
              </summary>
              <IssueList issues={c.issues} />
              {c.count > c.issues.length && (
                <p className="example-more body-medium">…и ещё {c.count - c.issues.length} в полном отчёте</p>
              )}
            </details>
          );
        })}
        {!all && (
          <md-text-button class="more" onClick={() => setAll(true)}>
            Показать все разделы ({cats.length})
          </md-text-button>
        )}
      </div>

      <div className="example-cta">
        <Link to="/coursework" className="link-btn">
          <md-filled-button><Icon name="upload" slot="icon" />Проверить свою курсовую</md-filled-button>
        </Link>
        <Link to="/vkr" className="link-btn">
          <md-outlined-button><Icon name="upload" slot="icon" />Проверить ВКР</md-outlined-button>
        </Link>
      </div>
    </section>
  );
}

/** Частые вопросы — тот же текст сервер отдаёт поисковикам с разметкой FAQPage (seo.py). */
export function Faq() {
  return (
    <section className="faq" aria-labelledby="faq-title">
      <h2 id="faq-title" className="headline-small">Частые вопросы</h2>
      {home.faq.map((f) => (
        <details key={f.q} className="accordion">
          <summary className="title-medium">
            <span>{f.q}</span>
            <span className="chevron"><Icon name="chevron" /></span>
          </summary>
          <p className="faq-answer body-large"><Rich text={f.a} /></p>
        </details>
      ))}
    </section>
  );
}
