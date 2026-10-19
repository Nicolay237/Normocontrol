import { useEffect } from "react";
import { Link } from "react-router-dom";
import gost from "../../../content/gost.json"; // тот же текст сервер отдаёт поисковикам (seo.py)
import { Icon } from "../ui.jsx";

export default function Gost() {
  useEffect(() => { document.title = `${gost.title} — Нормоконтроль`; }, []);

  return (
    <article className="container page article">
      <p className="label-large eyebrow">Справка</p>
      <h1 className="display-small hero-title">{gost.title}</h1>
      <p className="body-large supporting">{gost.intro}</p>

      <nav className="toc" aria-label="Содержание">
        {gost.sections.map((s) => (
          <a key={s.id} href={`#${s.id}`} className="chip label-large">{s.heading}</a>
        ))}
      </nav>

      {gost.sections.map((s) => (
        <section key={s.id} id={s.id} className="article-section">
          <h2 className="title-large">
            {s.heading} <span className="clause label-medium">{s.clause}</span>
          </h2>
          <ul className="article-list body-large">
            {s.items.map((it) => <li key={it}>{it}</li>)}
          </ul>
        </section>
      ))}

      <section className="article-section">
        <h2 className="title-large">Частые вопросы</h2>
        {gost.faq.map((f) => (
          <details key={f.q} className="accordion faq">
            <summary className="title-medium">
              <span>{f.q}</span>
              <span className="chevron"><Icon name="chevron" /></span>
            </summary>
            <p className="body-large faq-answer">{f.a}</p>
          </details>
        ))}
      </section>

      <div className="cta">
        <div>
          <h2 className="title-large">Проверьте свою работу</h2>
          <p className="body-medium muted">Загрузите .docx или .pdf — сервис найдёт отклонения от этих требований.</p>
        </div>
        <div className="row-actions">
          <Link to="/vkr" className="link-btn">
            <md-filled-button><Icon name="vkr" slot="icon" />Проверить ВКР</md-filled-button>
          </Link>
          <Link to="/coursework" className="link-btn">
            <md-outlined-button><Icon name="coursework" slot="icon" />Проверить курсовую</md-outlined-button>
          </Link>
        </div>
      </div>
    </article>
  );
}
