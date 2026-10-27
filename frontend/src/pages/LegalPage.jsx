import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLegal } from "../api.js";
import { Icon } from "../ui.jsx";

export const LEGAL_LINKS = [
  ["/offer", "Публичная оферта"],
  ["/refund", "Правила возврата"],
  ["/privacy", "Политика конфиденциальности"],
  ["/consent", "Согласие на обработку ПД"],
  ["/contacts", "Контакты и реквизиты"],
];

/** Текст документа: [[/путь|текст]] — внутренняя ссылка. */
export function Rich({ text }) {
  const parts = [];
  const rx = /\[\[(\/[a-z-]*)\|([^\]]+)\]\]/g;
  let pos = 0;
  let m;
  while ((m = rx.exec(text))) {
    parts.push(text.slice(pos, m.index));
    parts.push(<Link key={m.index} to={m[1]}>{m[2]}</Link>);
    pos = m.index + m[0].length;
  }
  parts.push(text.slice(pos));
  return <>{parts}</>;
}

/** Оферта, политика ПД, согласие, правила возврата, контакты — текст с сервера (реквизиты из .env). */
export default function LegalPage({ doc }) {
  const [state, setState] = useState({ data: null, error: null });

  useEffect(() => {
    setState({ data: null, error: null });
    fetchLegal(doc)
      .then((data) => {
        setState({ data, error: null });
        document.title = `${data.title} — Нормоконтроль`;
      })
      .catch((e) => setState({ data: null, error: e.message }));
    window.scrollTo({ top: 0 });
  }, [doc]);

  const { data, error } = state;
  return (
    <section className="container page legal">
      {error && <div className="banner banner-error body-medium" role="alert"><Icon name="error" /> {error}</div>}
      {!data && !error && <div className="loading"><md-circular-progress indeterminate="" /></div>}
      {data && (
        <article>
          <h1 className="headline-medium">{data.title}</h1>
          <p className="body-large supporting"><Rich text={data.intro} /></p>
          {data.sections.map((s) => (
            <section key={s.h}>
              <h2 className="title-large">{s.h}</h2>
              {s.blocks.map(([kind, val], i) => kind === "p"
                ? <p key={i} className="body-large"><Rich text={val} /></p>
                : (
                  <ul key={i} className="body-large">
                    {val.map((item) => <li key={item}><Rich text={item} /></li>)}
                  </ul>
                ))}
            </section>
          ))}
        </article>
      )}
      <nav className="legal-nav label-large" aria-label="Документы">
        {LEGAL_LINKS.filter(([to]) => to !== `/${doc}`).map(([to, title]) => <Link key={to} to={to}>{title}</Link>)}
      </nav>
    </section>
  );
}
