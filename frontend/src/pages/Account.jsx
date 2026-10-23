import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate, Link } from "react-router-dom";
import { accountOrders, changePassword, logout } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

export default function Account() {
  const { user, setSession } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ current: "", next: "", repeat: "" });
  const [state, setState] = useState({ busy: false, error: null, done: false });
  const [orders, setOrders] = useState([]);
  useEffect(() => { if (user) accountOrders().then((r) => setOrders(r.orders)).catch(() => {}); }, [user?.id]);

  useEffect(() => { document.title = "Аккаунт — Нормоконтроль"; }, []);
  if (!user) return <Navigate to="/login" replace state={{ from: "/account" }} />;

  const first = user.must_change_password;
  const mismatch = form.repeat && form.next !== form.repeat;

  async function submit(e) {
    e.preventDefault();
    if (mismatch) return;
    setState({ busy: true, error: null, done: false });
    try {
      const res = await changePassword(form.current, form.next);
      setSession(res);
      setForm({ current: "", next: "", repeat: "" });
      setState({ busy: false, error: null, done: true });
      if (first) navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setState({ busy: false, error: err.message, done: false });
    }
  }

  async function doLogout() {
    await logout().catch(() => {});
    setSession({ user: null, autofix_enabled: false });
    navigate("/", { replace: true });
  }

  return (
    <section className="container page narrow">
      <div className="auth-card">
        <span className="auth-icon"><Icon name={first ? "key" : "user"} /></span>
        <h1 className="headline-small">{first ? "Придумайте свой пароль" : user.name}</h1>
        <p className="body-medium muted">
          {first
            ? "Вы вошли с временным паролем от администратора. Задайте собственный — после этого откроется автоисправление."
            : <>Логин: <b>{user.login}</b>{user.role === "admin" && " · администратор"}</>}
        </p>
        {!first && user.email_verified === false && (
          <Link to="/verify" state={{ from: "/account" }} className="banner banner-error body-medium">
            <Icon name="mail" />
            <span>Почта не подтверждена — введите код из письма. Без этого оплата и автоисправление недоступны.</span>
          </Link>
        )}
        {!first && !user.free_autofix && user.autofix_credits > 0 && (
          <p className="body-medium access-note on">
            <Icon name="fix" size={18} />
            <span>Оплаченных исправлений: {user.autofix_credits}. Загрузите работу — и нажмите «Исправить».</span>
          </p>
        )}
        {!first && !user.free_autofix && user.subscription?.active && (
          <p className="body-medium access-note on">
            <Icon name="fix" size={18} />
            <span>
              Подписка до {new Date(user.subscription.until).toLocaleDateString("ru-RU")}:
              в этом месяце использовано {user.subscription.used} из {user.subscription.limit} исправлений.
            </span>
          </p>
        )}
        {!first && !(user.subscription?.active && !user.free_autofix) && (
          <p className={`body-medium access-note${user.free_autofix ? " on" : ""}`}>
            <Icon name={user.free_autofix ? "gift" : "fix"} size={18} />
            <span>
              {user.free_autofix
                ? "Автоисправление для вас бесплатно."
                : <>Автоисправление — по оплате или по <Link to="/">подписке</Link>. Если вы преподаватель,
                    администратор может открыть бесплатный доступ.</>}
            </span>
          </p>
        )}

        {!first && user.role === "admin" && (
          <Link to="/admin" className="list-link label-large">
            <Icon name="users" size={20} /> Управление учётными записями <Icon name="forward" size={18} />
          </Link>
        )}

        {!first && orders.length > 0 && (
          <div className="my-orders">
            <h2 className="title-medium">Мои оплаты</h2>
            <ul className="body-medium">
              {orders.map((o) => (
                <li key={o.id}>
                  <span>{o.paid_at ? new Date(o.paid_at).toLocaleDateString("ru-RU") : ""} · {o.title} · {o.amount}&nbsp;₽</span>
                  {o.receipt_url
                    ? <a href={o.receipt_url} target="_blank" rel="noreferrer">Чек</a>
                    : <span className="muted label-medium">чек будет отправлен на почту</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <form className="form" onSubmit={submit} onKeyDown={submitOnEnter}>
          {!first && <h2 className="title-medium">Сменить пароль</h2>}
          <Field
            label={first ? "Временный пароль" : "Текущий пароль"} type="password" autoComplete="current-password"
            required value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })}
          />
          <Field
            label="Новый пароль" type="password" autoComplete="new-password" required minLength={8}
            hint="Не короче 8 символов" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })}
          />
          <Field
            label="Повторите новый пароль" type="password" autoComplete="new-password" required
            error={mismatch ? "Пароли не совпадают" : null}
            value={form.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })}
          />
          {state.error && (
            <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
          )}
          {state.done && (
            <div className="banner banner-ok body-medium" role="status"><Icon name="ok" /><span>Пароль изменён.</span></div>
          )}
          <md-filled-button type="submit" class="wide" disabled={attr(state.busy || mismatch)}>
            <Icon name="key" slot="icon" />
            {state.busy ? "Сохраняем…" : "Сохранить пароль"}
          </md-filled-button>
        </form>

        <md-text-button onClick={doLogout} class="logout">
          <Icon name="logout" slot="icon" />
          Выйти из аккаунта
        </md-text-button>
      </div>
    </section>
  );
}
