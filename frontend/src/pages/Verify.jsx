import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { resendCode, verifyEmail } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

const COOLDOWN = 60; // секунд до повторной отправки

/** Подтверждение почты: код из 6 цифр из письма. */
export default function Verify() {
  const { user, setSession } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const back = location.state?.from || "/";
  const [code, setCode] = useState("");
  const [state, setState] = useState({
    busy: false, error: location.state?.mailSent === false
      ? "Письмо не удалось отправить — нажмите «Отправить код ещё раз»." : null,
    info: null,
  });
  const [wait, setWait] = useState(location.state?.mailSent === false ? 0 : COOLDOWN);

  useEffect(() => { document.title = "Подтверждение почты — Нормоконтроль"; }, []);
  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  if (!user) return <Navigate to="/login" replace state={{ from: "/verify" }} />;
  if (user.email_verified && !state.busy) return <Navigate to={back} replace />;

  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, error: null, info: null });
    try {
      const res = await verifyEmail(code);
      setSession(res);
      navigate(back, { replace: true });
    } catch (err) {
      setState({ busy: false, error: err.message, info: null });
    }
  }

  async function resend() {
    setState({ busy: false, error: null, info: null });
    try {
      await resendCode();
      setCode("");
      setWait(COOLDOWN);
      setState({ busy: false, error: null, info: "Новый код отправлен. Предыдущий больше не действует." });
    } catch (err) {
      setState({ busy: false, error: err.message, info: null });
    }
  }

  return (
    <section className="container page narrow">
      <div className="auth-card">
        <span className="auth-icon"><Icon name="mail" /></span>
        <h1 className="headline-small">Подтвердите почту</h1>
        <p className="body-medium muted">
          Мы отправили код из 6 цифр на <b>{user.login}</b>. Если письма нет — проверьте папку «Спам».
        </p>
        <form className="form" onSubmit={submit} onKeyDown={submitOnEnter}>
          <Field
            label="Код из письма" name="code" inputMode="numeric" autoComplete="one-time-code" autoFocus required
            maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          />
          {state.error && (
            <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
          )}
          {state.info && (
            <div className="banner banner-ok body-medium" role="status"><Icon name="ok" /><span>{state.info}</span></div>
          )}
          <md-filled-button type="submit" class="wide" disabled={attr(state.busy || code.length !== 6)}>
            <Icon name="ok" slot="icon" />
            {state.busy ? "Проверяем…" : "Подтвердить"}
          </md-filled-button>
        </form>
        <md-text-button onClick={resend} disabled={attr(wait > 0)}>
          <Icon name="reset" slot="icon" />
          {wait > 0 ? `Отправить код ещё раз через ${wait} с` : "Отправить код ещё раз"}
        </md-text-button>
      </div>
    </section>
  );
}
