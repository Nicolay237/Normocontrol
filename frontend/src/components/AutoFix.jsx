import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fixFile, fixedUrl } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Icon, attr } from "../ui.jsx";
import { IssueList, plural } from "./ReportView.jsx";
import Progress from "./Progress.jsx";

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

export default function AutoFix({ file, uploadId, profileKey }) {
  const [state, setState] = useState({ phase: "idle", result: null, error: null, upload: null });
  const { user, autofixEnabled, setSession } = useSession();
  const location = useLocation();
  const isDocx = /\.docx$/i.test(file?.name ?? "");

  async function run() {
    setState({ phase: "loading", result: null, error: null, upload: null });
    try {
      const result = await fixFile({
        uploadId, file, profile: profileKey,
        // прогресс появится, только если файл придётся отправить заново
        onProgress: (upload) => setState((s) => ({ ...s, upload })),
      });
      setState({ phase: "done", result, error: null, upload: null });
    } catch (e) {
      if (e.code === "login_required") setSession({ user: null, autofix_enabled: false }); // сессия истекла
      setState({ phase: "idle", result: null, error: e.message, upload: null });
    }
  }

  if (!isDocx)
    return (
      <Card icon="fix">
        <h2 className="title-large">Автоисправление недоступно для PDF</h2>
        <p className="body-medium">Загрузите исходный документ Word (.docx) — его можно исправить автоматически.</p>
      </Card>
    );

  if (!user)
    return (
      <Card icon="lock">
        <h2 className="title-large">Автоисправление — для университета</h2>
        <p className="body-medium">
          Сотрудники и студенты университета исправляют оформление бесплатно — войдите с логином от кафедры.
          Для остальных автоисправление скоро станет доступно платно.
        </p>
        <Link to="/login" state={{ from: location.pathname }} className="link-btn">
          <md-filled-button>
            <Icon name="login" slot="icon" />
            Войти
          </md-filled-button>
        </Link>
      </Card>
    );

  if (!autofixEnabled)
    return (
      <Card icon="key">
        <h2 className="title-large">Смените временный пароль</h2>
        <p className="body-medium">Автоисправление откроется, как только вы зададите собственный пароль.</p>
        <Link to="/account" state={{ from: location.pathname }} className="link-btn">
          <md-filled-button>
            <Icon name="key" slot="icon" />
            Задать пароль
          </md-filled-button>
        </Link>
      </Card>
    );

  if (state.phase === "done") {
    const r = state.result;
    const remaining = r.remaining.flatMap((c) => c.issues);
    const fixedCats = r.categories.filter((c) => c.fixed > 0);
    return (
      <Card icon="ok" done>
        <h2 className="title-large">
          Исправлено {r.total_fixed} {plural(r.total_fixed)} из {r.issues_before}
        </h2>
        <p className="body-medium">
          {r.issues_after === 0
            ? "Замечаний не осталось. Исходный файл не изменён."
            : `Осталось ${r.issues_after} — их нужно поправить вручную. Исходный файл не изменён.`}
        </p>

        <md-filled-button href={fixedUrl(r.download_id)} download="">
          <Icon name="download" slot="icon" />
          Скачать исправленный файл
        </md-filled-button>

        {fixedCats.length > 0 && (
          <details className="fix-details">
            <summary className="label-large">
              Что исправлено <span className="chevron"><Icon name="chevron" size={20} /></span>
            </summary>
            <ul className="applied-list">
              {fixedCats.map((c) => (
                <li key={c.name} className="body-medium">
                  <Icon name="tick" size={18} />
                  <span>{c.name}</span>
                  <b className="label-medium">{c.fixed === c.before ? `все ${c.fixed}` : `${c.fixed} из ${c.before}`}</b>
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
      {loading ? (
        <Progress upload={state.upload} uploadingText="Отправляем файл" workingText="Исправляем оформление…" />
      ) : (
        <md-filled-button onClick={run} disabled={attr(loading)}>
          <Icon name="fix" slot="icon" />
          Исправить и скачать
        </md-filled-button>
      )}
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
      )}
    </Card>
  );
}
