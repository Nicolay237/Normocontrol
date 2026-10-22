import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { login, register } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

/** Вход (/login) и регистрация (/register) — одна карточка, разные поля. */
export default function Login({ mode = "login" }) {
  const isRegister = mode === "register";
  const { user, setSession } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const back = location.state?.from || "/";
  const [form, setForm] = useState({ login: "", name: "", password: "", consent: false });
  const [show, setShow] = useState(false);
  const [state, setState] = useState({ busy: false, error: null });

  useEffect(() => {
    document.title = (isRegister ? "Регистрация" : "Вход") + " — Нормоконтроль";
    setState({ busy: false, error: null });
  }, [isRegister]);
  if (user && !state.busy)
    return <Navigate to={user.must_change_password ? "/account" : user.email_verified === false ? "/verify" : back}
                     replace state={{ from: back }} />;

  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, error: null });
    try {
      const res = isRegister
        ? await register(form.login, form.password, form.name, form.consent)
        : await login(form.login, form.password);
      setSession(res);
      const next = res.user.must_change_password ? "/account" : res.user.email_verified === false ? "/verify" : back;
      navigate(next, { replace: true, state: { from: back, mailSent: res.mail_sent } });
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <section className="container page narrow">
      <div className="auth-card">
        <span className="auth-icon"><Icon name={isRegister ? "userAdd" : "login"} /></span>
        <h1 className="headline-small">{isRegister ? "Регистрация" : "Вход"}</h1>
        <p className="body-medium muted">
          {isRegister
            ? "Аккаунт нужен, чтобы исправлять работы и возвращаться к ним. Проверка оформления доступна и без него."
            : "Войдите по email или по логину, который выдал администратор кафедры."}
        </p>
        <form className="form" onSubmit={submit} onKeyDown={submitOnEnter}>
          {isRegister && (
            <Field label="Как к вам обращаться (необязательно)" name="name" autoComplete="name"
                   value={form.name} onChange={set("name")} />
          )}
          <Field
            label={isRegister ? "Email" : "Email или логин"} name={isRegister ? "email" : "username"}
            type={isRegister ? "email" : "text"} autoComplete={isRegister ? "email" : "username"}
            autoCapitalize="none" spellCheck={false} required autoFocus value={form.login} onChange={set("login")}
          />
          <div className="field-with-action">
            <Field
              label="Пароль" name="password" type={show ? "text" : "password"}
              autoComplete={isRegister ? "new-password" : "current-password"} required minLength={isRegister ? 8 : undefined}
              hint={isRegister ? "Не короче 8 символов" : undefined} value={form.password} onChange={set("password")}
            />
            <button type="button" className="icon-btn" onClick={() => setShow(!show)}
                    aria-label={show ? "Скрыть пароль" : "Показать пароль"}>
              <Icon name={show ? "eyeOff" : "eye"} size={20} />
            </button>
          </div>
          {isRegister && (
            <label className="check consent body-medium">
              <input type="checkbox" required checked={form.consent}
                     onChange={(e) => setForm({ ...form, consent: e.target.checked })} />
              <span>
                Принимаю условия <Link to="/offer" target="_blank">оферты</Link> и даю{" "}
                <Link to="/consent" target="_blank">согласие на обработку персональных данных</Link> в соответствии
                с <Link to="/privacy" target="_blank">политикой конфиденциальности</Link>
              </span>
            </label>
          )}
          {state.error && (
            <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
          )}
          <md-filled-button type="submit" class="wide" disabled={attr(state.busy || (isRegister && !form.consent))}>
            <Icon name={isRegister ? "userAdd" : "login"} slot="icon" />
            {isRegister
              ? (state.busy ? "Создаём аккаунт…" : "Зарегистрироваться")
              : (state.busy ? "Входим…" : "Войти")}
          </md-filled-button>
        </form>
        <p className="body-medium muted small-note">
          {isRegister
            ? <>Уже есть аккаунт? <Link to="/login" state={location.state}>Войти</Link></>
            : <>Нет аккаунта? <Link to="/register" state={location.state}>Зарегистрируйтесь</Link> — это минута.
                <br /><Link to="/forgot">Забыли пароль?</Link></>}
        </p>
      </div>
    </section>
  );
}
