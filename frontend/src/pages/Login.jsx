import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { login } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

export default function Login() {
  const { user, setSession } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const back = location.state?.from || "/";
  const [form, setForm] = useState({ login: "", password: "" });
  const [show, setShow] = useState(false);
  const [state, setState] = useState({ busy: false, error: null });

  useEffect(() => { document.title = "Вход — Нормоконтроль"; }, []);
  if (user && !state.busy) return <Navigate to={user.must_change_password ? "/account" : back} replace />;

  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, error: null });
    try {
      const res = await login(form.login, form.password);
      setSession(res);
      navigate(res.user.must_change_password ? "/account" : back, { replace: true, state: { from: back } });
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  return (
    <section className="container page narrow">
      <div className="auth-card">
        <span className="auth-icon"><Icon name="login" /></span>
        <h1 className="headline-small">Вход для университета</h1>
        <p className="body-medium muted">
          Логин и пароль выдаёт администратор кафедры. После входа автоисправление оформления доступно бесплатно.
        </p>
        <form className="form" onSubmit={submit} onKeyDown={submitOnEnter}>
          <Field
            label="Логин" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false}
            required autoFocus value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })}
          />
          <div className="field-with-action">
            <Field
              label="Пароль" name="password" type={show ? "text" : "password"} autoComplete="current-password"
              required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <button type="button" className="icon-btn" onClick={() => setShow(!show)}
                    aria-label={show ? "Скрыть пароль" : "Показать пароль"}>
              <Icon name={show ? "eyeOff" : "eye"} size={20} />
            </button>
          </div>
          {state.error && (
            <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
          )}
          <md-filled-button type="submit" class="wide" disabled={attr(state.busy)}>
            <Icon name="login" slot="icon" />
            {state.busy ? "Входим…" : "Войти"}
          </md-filled-button>
        </form>
        <p className="body-medium muted small-note">
          Нет логина? Обратитесь к администратору кафедры. Проверка оформления доступна и без входа.
        </p>
      </div>
    </section>
  );
}
