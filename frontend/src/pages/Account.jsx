import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate, Link } from "react-router-dom";
import { accountOrders, changePassword, logout } from "../api.js";
import { useProfiles, useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";
import useBuy from "../components/useBuy.js";

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("ru-RU") : "—");

/** Смена пароля: при первом входе — сразу, в кабинете — по кнопке. */
function PasswordForm({ first, onDone }) {
  const { setSession } = useSession();
  const [form, setForm] = useState({ current: "", next: "", repeat: "" });
  const [state, setState] = useState({ busy: false, error: null, done: false });
  const mismatch = form.repeat && form.next !== form.repeat;

  async function submit(e) {
    e.preventDefault();
    if (mismatch) return;
    setState({ busy: true, error: null, done: false });
    try {
      setSession(await changePassword(form.current, form.next));
      setForm({ current: "", next: "", repeat: "" });
      setState({ busy: false, error: null, done: true });
      onDone?.();
    } catch (err) {
      setState({ busy: false, error: err.message, done: false });
    }
  }

  return (
    <form className="form" onSubmit={submit} onKeyDown={submitOnEnter}>
      <Field label={first ? "Временный пароль" : "Текущий пароль"} type="password" autoComplete="current-password"
             required value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
      <Field label="Новый пароль" type="password" autoComplete="new-password" required minLength={8}
             hint="Не короче 8 символов" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
      <Field label="Повторите новый пароль" type="password" autoComplete="new-password" required
             error={mismatch ? "Пароли не совпадают" : null}
             value={form.repeat} onChange={(e) => setForm({ ...form, repeat: e.target.value })} />
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
      )}
      {state.done && (
        <div className="banner banner-ok body-medium" role="status"><Icon name="ok" /><span>Пароль изменён.</span></div>
      )}
      <md-filled-button type="submit" disabled={attr(state.busy || mismatch)}>
        <Icon name="key" slot="icon" />
        {state.busy ? "Сохраняем…" : "Сохранить пароль"}
      </md-filled-button>
    </form>
  );
}

/** Доступ к автоисправлению: бесплатный, оплаченные исправления, подписка — карточками, как тарифы. */
function Access({ user }) {
  const { config } = useProfiles();
  const { buy, busy, error, soon } = useBuy();
  const sub = user.subscription || {};
  const price = config.autofix_price ?? 99;
  const subPrice = config.subscription_price ?? 299;

  if (user.free_autofix)
    return (
      <div className="price-grid account-access">
        <div className="card card-link price-card featured">
          <span className="card-icon"><Icon name="gift" /></span>
          <span className="label-large">Автоисправление</span>
          <span className="price-value headline-medium">Бесплатно</span>
          <p className="body-medium">
            {user.role === "admin" ? "Вы администратор." : "Доступ открыл администратор."} Исправляйте сколько нужно.
          </p>
        </div>
      </div>
    );

  return (
    <>
      <div className="price-grid account-access">
        <div className={`card card-link price-card${user.autofix_credits > 0 ? " featured" : " card-filled"}`}>
          <span className="card-icon"><Icon name="fix" /></span>
          <span className="label-large">Оплаченные исправления</span>
          <span className="price-value headline-medium">{user.autofix_credits || 0}</span>
          <p className="body-medium">
            {user.autofix_credits > 0
              ? "Загрузите работу и нажмите «Исправить» — исправление спишется автоматически."
              : `Разовое автоисправление одной работы — ${price} ₽.`}
          </p>
          <md-filled-tonal-button disabled={attr(busy)} onClick={() => buy("autofix")}>
            {busy === "autofix" ? "Переходим к оплате…" : `Купить за ${price} ₽`}
          </md-filled-tonal-button>
        </div>

        <div className={`card card-link price-card${sub.active ? " featured" : " card-filled"}`}>
          <span className="card-icon"><Icon name="check" /></span>
          <span className="label-large">Подписка</span>
          {sub.active ? (
            <>
              <span className="price-value headline-medium">{sub.left} из {sub.limit}</span>
              <p className="body-medium">
                Осталось исправлений в этом месяце. Подписка действует до <b>{fmtDate(sub.until)}</b>.
              </p>
              <div className="meter" role="img" aria-label={`Использовано ${sub.used} из ${sub.limit}`}>
                <span style={{ width: `${Math.min(100, (sub.used / sub.limit) * 100)}%` }} />
              </div>
              <md-filled-tonal-button disabled={attr(busy)} onClick={() => buy("subscription")}>
                {busy === "subscription" ? "Переходим к оплате…" : `Продлить на 30 дней — ${subPrice} ₽`}
              </md-filled-tonal-button>
            </>
          ) : (
            <>
              <span className="price-value headline-medium">{subPrice}&nbsp;₽<span className="body-medium"> / месяц</span></span>
              <p className="body-medium">
                {config.subscription_limit ?? 30} автоисправлений в месяц — исправляйте работу после каждой правки.
              </p>
              <md-filled-button disabled={attr(busy)} onClick={() => buy("subscription")}>
                {busy === "subscription" ? "Переходим к оплате…" : "Оформить подписку"}
              </md-filled-button>
            </>
          )}
        </div>
      </div>
      {error && <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{error}</span></div>}
      {soon && (
        <div className="banner banner-info body-medium" role="status">
          <Icon name="info" /><span>Оплата подключается и заработает в ближайшие дни.</span>
        </div>
      )}
      <p className="body-medium muted">
        Вы преподаватель? Сообщите администратору свой логин <b>{user.login}</b> — он откроет бесплатный доступ.
      </p>
    </>
  );
}

function Orders({ orders }) {
  if (orders === null) return <div className="loading"><md-circular-progress indeterminate="" /></div>;
  if (!orders.length) return <p className="body-medium muted">Оплат пока нет.</p>;
  return (
    <ul className="user-list">
      {orders.map((o) => (
        <li key={o.id} className="user-row">
          <div className="user-main">
            <span className="title-medium">{o.amount}&nbsp;₽ · {o.title}</span>
            <span className="body-medium muted">оплачено {fmtDate(o.paid_at)}</span>
          </div>
          {o.receipt_url ? (
            <md-filled-tonal-button href={o.receipt_url} target="_blank">
              <Icon name="file" slot="icon" />
              Открыть чек
            </md-filled-tonal-button>
          ) : (
            <span className="tag">чек придёт на почту</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function Account() {
  const { user, setSession } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [orders, setOrders] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => { document.title = "Личный кабинет — Нормоконтроль"; }, []);
  useEffect(() => {
    if (user && !user.must_change_password) accountOrders().then((r) => setOrders(r.orders)).catch(() => setOrders([]));
  }, [user?.id, user?.must_change_password]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!user) return <Navigate to="/login" replace state={{ from: "/account" }} />;

  async function doLogout() {
    await logout().catch(() => {});
    setSession({ user: null, autofix_enabled: false });
    navigate("/", { replace: true });
  }

  // первый вход с временным паролем от администратора — только смена пароля
  if (user.must_change_password)
    return (
      <section className="container page narrow">
        <div className="auth-card">
          <span className="auth-icon"><Icon name="key" /></span>
          <h1 className="headline-small">Придумайте свой пароль</h1>
          <p className="body-medium muted">
            Вы вошли с временным паролем от администратора. Задайте собственный — после этого откроется автоисправление.
          </p>
          <PasswordForm first onDone={() => navigate(location.state?.from || "/", { replace: true })} />
        </div>
      </section>
    );

  return (
    <section className="container page account">
      <p className="label-large eyebrow">Личный кабинет</p>
      <div className="account-head">
        <div>
          <h1 className="display-small hero-title">{user.name}</h1>
          <p className="body-large supporting">
            {user.login}{user.role === "admin" && " · администратор"}
          </p>
        </div>
        <div className="account-actions">
          {user.role === "admin" && (
            <Link to="/admin" className="link-btn">
              <md-filled-tonal-button><Icon name="users" slot="icon" />Администрирование</md-filled-tonal-button>
            </Link>
          )}
          <md-outlined-button onClick={() => setShowPassword(!showPassword)}>
            <Icon name="key" slot="icon" />
            {showPassword ? "Скрыть" : "Сменить пароль"}
          </md-outlined-button>
          <md-text-button onClick={doLogout}>
            <Icon name="logout" slot="icon" />
            Выйти
          </md-text-button>
        </div>
      </div>

      {user.email_verified === false && (
        <Link to="/verify" state={{ from: "/account" }} className="banner banner-error body-medium">
          <Icon name="mail" />
          <span>Почта не подтверждена — введите код из письма. Без этого оплата и автоисправление недоступны.</span>
        </Link>
      )}

      {showPassword && (
        <div className="panel account-password">
          <h2 className="title-large">Смена пароля</h2>
          <PasswordForm onDone={() => setTimeout(() => setShowPassword(false), 1500)} />
        </div>
      )}

      <div className="list-head"><h2 className="title-large">Автоисправление</h2></div>
      <Access user={user} />

      <div className="list-head">
        <h2 className="title-large">Оплаты и чеки {orders?.length > 0 && <span className="muted">({orders.length})</span>}</h2>
      </div>
      <p className="body-medium muted supporting">
        Чек самозанятого из «Мой налог» приходит на почту в течение нескольких дней после оплаты и появляется здесь.
      </p>
      <Orders orders={orders} />
    </section>
  );
}
