import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { forgotPassword, resetPassword } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

/** Сброс пароля: email → код из письма и новый пароль. */
export default function Forgot() {
  const { setSession } = useSession();
  const navigate = useNavigate();
  const [step, setStep] = useState("email");
  const [form, setForm] = useState({ email: "", code: "", password: "", repeat: "" });
  const [state, setState] = useState({ busy: false, error: null });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const mismatch = form.repeat && form.password !== form.repeat;

  useEffect(() => { document.title = "Восстановление пароля — Нормоконтроль"; }, []);

  async function sendCode(e) {
    e.preventDefault();
    setState({ busy: true, error: null });
    try {
      await forgotPassword(form.email);
      setStep("code");
      setState({ busy: false, error: null });
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  async function reset(e) {
    e.preventDefault();
    if (mismatch) return;
    setState({ busy: true, error: null });
    try {
      setSession(await resetPassword(form.email, form.code, form.password));
      navigate("/", { replace: true });
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  const error = state.error && (
    <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
  );

  return (
    <section className="container page narrow">
      <div className="auth-card">
        <span className="auth-icon"><Icon name="key" /></span>
        <h1 className="headline-small">Восстановление пароля</h1>
        {step === "email" ? (
          <>
            <p className="body-medium muted">Укажите email, с которым регистрировались, — пришлём код для сброса пароля.</p>
            <form className="form" onSubmit={sendCode} onKeyDown={submitOnEnter}>
              <Field label="Email" name="email" type="email" autoComplete="email" autoCapitalize="none"
                     spellCheck={false} required autoFocus value={form.email} onChange={set("email")} />
              {error}
              <md-filled-button type="submit" class="wide" disabled={attr(state.busy)}>
                <Icon name="mail" slot="icon" />
                {state.busy ? "Отправляем…" : "Получить код"}
              </md-filled-button>
            </form>
          </>
        ) : (
          <>
            <p className="body-medium muted">
              Если <b>{form.email}</b> зарегистрирован, на него пришёл код из 6 цифр. Проверьте и папку «Спам».
            </p>
            <form className="form" onSubmit={reset} onKeyDown={submitOnEnter}>
              <Field label="Код из письма" name="code" inputMode="numeric" autoComplete="one-time-code" required autoFocus
                     maxLength={6} value={form.code}
                     onChange={(e) => setForm({ ...form, code: e.target.value.replace(/\D/g, "").slice(0, 6) })} />
              <Field label="Новый пароль" type="password" autoComplete="new-password" required minLength={8}
                     hint="Не короче 8 символов" value={form.password} onChange={set("password")} />
              <Field label="Повторите пароль" type="password" autoComplete="new-password" required
                     error={mismatch ? "Пароли не совпадают" : null} value={form.repeat} onChange={set("repeat")} />
              {error}
              <md-filled-button type="submit" class="wide" disabled={attr(state.busy || mismatch || form.code.length !== 6)}>
                <Icon name="key" slot="icon" />
                {state.busy ? "Сохраняем…" : "Сохранить пароль и войти"}
              </md-filled-button>
            </form>
            <md-text-button onClick={() => { setStep("email"); setState({ busy: false, error: null }); }}>
              Указать другой email
            </md-text-button>
          </>
        )}
        <p className="body-medium muted small-note">
          Логин выдавал администратор кафедры? Сбросить пароль может он. <Link to="/login">Вернуться ко входу</Link>
        </p>
      </div>
    </section>
  );
}
