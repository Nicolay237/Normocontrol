import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fixFile, fixedUrl } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Icon, attr } from "../ui.jsx";
import { IssueList, plural } from "./ReportView.jsx";
import Progress from "./Progress.jsx";
import Offer from "./Offer.jsx";
import Celebration from "./Celebration.jsx";

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

export default function AutoFix({ file, uploadId, profileKey, standards, total = 0, fixable = 0 }) {
  const [state, setState] = useState({ phase: "idle", result: null, error: null, upload: null });
  const { user, autofixEnabled, setSession } = useSession();
  const location = useLocation();
  const isDocx = /\.docx$/i.test(file?.name ?? "");

  async function run() {
    setState({ phase: "loading", result: null, error: null, upload: null });
    try {
      const result = await fixFile({
        uploadId, file, profile: profileKey, standards,
        // прогресс появится, только если файл придётся отправить заново
        onProgress: (upload) => setState((s) => ({ ...s, upload })),
      });
      setState({ phase: "done", result, error: null, upload: null });
      // остаток лимита подписки — в шапку аккаунта и карточку
      if (result.subscription && user)
        setSession({ user: { ...user, subscription: result.subscription, autofix_credits: result.autofix_credits },
                     autofix_enabled: user.free_autofix || result.subscription.left > 0 || result.autofix_credits > 0 });
    } catch (e) {
      if (e.code === "login_required") setSession({ user: null, autofix_enabled: false }); // сессия истекла
      if (e.code === "payment_required" || e.code === "limit_reached")
        setSession({ user, autofix_enabled: false });   // доступ закрыли или лимит подписки исчерпан
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

  const offer = <Offer total={total} fixable={fixable} uploadId={uploadId} profileKey={profileKey}
                       standards={standards} fileName={file?.name} />;
  // Готовый результат показываем всегда: исправление могло потратить последнее оплаченное
  // исправление или последний лимит подписки — доступ закрылся, но скачать файл нужно.
  const done = state.phase === "done";
  if (!done && !user) return offer;

  if (!done && user.must_change_password)
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

  if (!done && user.email_verified === false)
    return (
      <Card icon="mail">
        <h2 className="title-large">Подтвердите почту</h2>
        <p className="body-medium">
          Мы отправили код на {user.login}. После подтверждения откроются оплата и автоисправление.
        </p>
        <Link to="/verify" state={{ from: location.pathname }} className="link-btn">
          <md-filled-button>
            <Icon name="mail" slot="icon" />
            Ввести код
          </md-filled-button>
        </Link>
      </Card>
    );

  const sub = user?.subscription;
  if (!done && !autofixEnabled && sub?.active)
    return (
      <Card icon="fix">
        <h2 className="title-large">Лимит подписки на этот месяц исчерпан</h2>
        <p className="body-medium">
          Использованы все {sub.limit} исправлений. Лимит обновится 1-го числа, подписка действует
          до {new Date(sub.until).toLocaleDateString("ru-RU")}. Пока можно скачать «Работу с отметками» выше.
        </p>
      </Card>
    );

  // вошёл, но бесплатного доступа и подписки нет — покупка
  if (!done && !autofixEnabled) return offer;

  if (done) {
    const r = state.result;
    const remaining = r.remaining.flatMap((c) => c.issues);
    const fixedCats = r.categories.filter((c) => c.fixed > 0);
    return (
      <Card icon="ok" done>
        {r.issues_after === 0 && <Celebration key={r.download_id} />}
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

        {r.autofix_credits > 0 && !user.free_autofix && (
          <p className="body-medium muted">Оплаченных исправлений осталось: {r.autofix_credits}.</p>
        )}
        {r.subscription?.active && !user.free_autofix && (
          <p className="body-medium muted">
            По подписке в этом месяце осталось {r.subscription.left} из {r.subscription.limit} исправлений.
          </p>
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
          Исправить
        </md-filled-button>
      )}
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
      )}
    </Card>
  );
}
