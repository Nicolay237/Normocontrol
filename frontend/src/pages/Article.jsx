import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { fixedUrl, formatArticle } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import UploadForm from "../components/UploadForm.jsx";
import Progress from "../components/Progress.jsx";
import { Icon } from "../ui.jsx";

const IDLE = { phase: "idle", result: null, error: null, upload: null };

const HIGHLIGHTS = [
  { icon: "font", label: "Times New Roman 14 пт" },
  { icon: "spacing", label: "Интервал 1,0" },
  { icon: "indent", label: "Отступ 0,5 см" },
  { icon: "margins", label: "Поля 1,29 / 1,9 / 2,5 см" },
];

const PARTS = [
  "УДК, название (24 пт), авторы с ФИО полужирным, организации, «Для цитирования»",
  "Аннотация, ключевые слова, шифр специальности — 12 пт",
  "Разделы — 14 пт, полужирные малые прописные; текст — по ширине, отступ 0,5 см",
  "«Таблица N» справа курсивом, название по центру, текст таблиц 11 пт",
  "Подписи «Рис. N. Название» по центру, без точки в конце",
  "«СПИСОК ИСТОЧНИКОВ» и записи — 12 пт; английский блок и REFERENCES",
  "Кавычки «ёлочки», тире вместо дефисов, «е» вместо «ё»",
];

/**
 * Оформление статьи по правилам журнала «Интеллектуальные технологии на транспорте».
 * Не продаётся: страница доступна тем, кому администратор открыл «Статьи».
 */
export default function Article() {
  const { user } = useSession();
  const [state, setState] = useState(IDLE);

  useEffect(() => { document.title = "Оформление статьи — Нормоконтроль"; }, []);

  if (!user) return <Navigate to="/login" replace state={{ from: "/article" }} />;
  if (!user.article_access)
    return (
      <section className="container page narrow">
        <div className="auth-card">
          <span className="auth-icon"><Icon name="lock" /></span>
          <h1 className="headline-small">Функция для кафедры</h1>
          <p className="body-medium muted">
            Оформление статей по правилам журнала открывает администратор сайта. Если вы сотрудник
            или аспирант кафедры, попросите открыть доступ для вашего аккаунта.
          </p>
        </div>
      </section>
    );

  async function onSubmit(file) {
    setState({ phase: "loading", result: null, error: null, upload: 0 });
    try {
      const result = await formatArticle(file, (upload) => setState((s) => ({ ...s, upload })));
      setState({ phase: "done", result, error: null, upload: null });
      window.scrollTo({ top: 0 });
    } catch (e) {
      setState({ ...IDLE, error: e.message });
    }
  }

  if (state.phase === "done") {
    const r = state.result;
    return (
      <section className="container page">
        <div className="report">
          <div className="summary summary-clean">
            <span className="summary-icon ok"><Icon name="ok" /></span>
            <div className="summary-text">
              <h1 className="headline-small">Статья оформлена</h1>
              <div className="title-medium summary-file">{r.file}</div>
              <div className="body-medium summary-meta">
                Правила журнала «Интеллектуальные технологии на транспорте»
              </div>
            </div>
            <div className="summary-actions">
              <md-filled-button href={fixedUrl(r.download_id)} download="">
                <Icon name="download" slot="icon" />
                Скачать статью
              </md-filled-button>
            </div>
          </div>

          {r.warnings.length > 0 && (
            <>
              <h2 className="title-large section-title">Проверьте и поправьте вручную</h2>
              <ul className="article-list article-warn">
                {r.warnings.map((w) => (
                  <li key={w} className="body-medium"><Icon name="hint" size={20} /><span>{w}</span></li>
                ))}
              </ul>
            </>
          )}

          <h2 className="title-large section-title">Что сделано</h2>
          <ul className="article-list">
            {r.done.map((d) => (
              <li key={d.name} className="body-medium">
                <Icon name="tick" size={20} />
                <span>{d.name}{d.count > 1 && <span className="muted"> · {d.count}</span>}</span>
              </li>
            ))}
          </ul>
          <p className="body-medium muted article-note">
            Файл хранится на сервере час — скачайте его сразу. Перед отправкой в редакцию откройте статью
            в Word и пролистайте: формулы и рисунки сервис не перестраивает.
          </p>
        </div>
        <div className="reset">
          <md-text-button onClick={() => setState(IDLE)}>
            <Icon name="back" slot="icon" />
            Оформить другую статью
          </md-text-button>
        </div>
      </section>
    );
  }

  return (
    <section className="container page">
      <header className="hero">
        <span className="hero-art" aria-hidden="true"><Icon name="file" size={176} /></span>
        <span className="hero-badge label-large"><Icon name="lock" size={18} /> Для кафедры</span>
        <h1 className="display-small hero-heading">Оформление статьи</h1>
        <p className="body-large hero-tagline">
          По правилам журнала «Интеллектуальные технологии на транспорте»: загрузите статью в Word —
          получите файл, оформленный по шаблону редакции.
        </p>
        <ul className="highlights" aria-label="Основные требования">
          {HIGHLIGHTS.map((h) => (
            <li key={h.icon} className="highlight label-large"><Icon name={h.icon} size={18} />{h.label}</li>
          ))}
        </ul>
      </header>

      <div className="banner banner-info body-medium">
        <Icon name="hint" />
        <span>
          <b>Загрузите статью целиком</b> — от УДК до английского блока и REFERENCES. Части статьи
          сервис узнаёт по словам «Аннотация», «Ключевые слова», «Для цитирования», «Список источников»,
          «Abstract» и по порядку; заголовки разделов — по стилю «Заголовок» или полужирному шрифту.
        </span>
      </div>

      {state.phase === "loading" ? (
        <Progress upload={state.upload} workingText="Оформляем статью…" hint="Обычно несколько секунд." />
      ) : (
        <UploadForm onSubmit={onSubmit} serverError={state.error} docxOnly submitLabel="Оформить статью" />
      )}

      <h2 className="title-large section-title">Что оформляется</h2>
      <ul className="article-list">
        {PARTS.map((p) => (
          <li key={p} className="body-medium"><Icon name="tick" size={20} /><span>{p}</span></li>
        ))}
      </ul>
    </section>
  );
}
