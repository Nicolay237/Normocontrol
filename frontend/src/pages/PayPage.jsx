import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { fetchOrder } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import AutoFix from "../components/AutoFix.jsx";
import { Icon } from "../ui.jsx";

const POLL_MS = 2500;
const POLL_FOR_MS = 5 * 60 * 1000; // СБП и 3-D Secure иногда подтверждаются не сразу

const PROFILE_PATH = { vkr: "/vkr", coursework: "/coursework", custom: "/standards" };

/** Сюда ЮKassa возвращает покупателя после оплаты: ждём подтверждения и выдаём оплаченное. */
export default function PayPage() {
  const { orderId } = useParams();
  const { user, setSession } = useSession();
  const [state, setState] = useState({ order: null, error: null, waited: 0 });

  useEffect(() => { document.title = "Оплата — Нормоконтроль"; }, []);

  useEffect(() => {
    if (!user) return undefined;
    let stop = false;
    let timer;
    const started = Date.now();
    async function poll() {
      try {
        const res = await fetchOrder(orderId);
        if (stop) return;
        setSession(res);
        setState({ order: res.order, error: null, waited: Date.now() - started });
        if (res.order.status === "pending" && Date.now() - started < POLL_FOR_MS) timer = setTimeout(poll, POLL_MS);
      } catch (e) {
        if (!stop) setState((s) => ({ ...s, error: e.message }));
      }
    }
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, [orderId, !!user]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return <Navigate to="/login" replace state={{ from: `/pay/${orderId}` }} />;
  const { order, error } = state;

  return (
    <section className="container page narrow">
      {error && !order && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{error}</span></div>
      )}
      {!order && !error && <div className="loading"><md-circular-progress indeterminate="" /></div>}

      {order?.status === "pending" && (
        <div className="auth-card">
          <span className="auth-icon"><Icon name="info" /></span>
          <h1 className="headline-small">Ждём подтверждения оплаты</h1>
          <p className="body-medium muted">
            Обычно это занимает несколько секунд. Страница обновится сама — закрывать её не нужно.
            {state.waited >= POLL_FOR_MS && " Если вы не завершили оплату, вернитесь к работе и оформите заказ ещё раз."}
          </p>
          {state.waited < POLL_FOR_MS && <div className="loading"><md-circular-progress indeterminate="" /></div>}
        </div>
      )}

      {order?.status === "canceled" && (
        <div className="auth-card">
          <span className="auth-icon"><Icon name="error" /></span>
          <h1 className="headline-small">Оплата не прошла</h1>
          <p className="body-medium muted">
            Деньги не списаны. Можно вернуться к работе и попробовать ещё раз — например, другой картой или через СБП.
          </p>
          <Link to={PROFILE_PATH[order.profile] || "/"} className="link-btn">
            <md-filled-button><Icon name="back" slot="icon" />Вернуться к проверке</md-filled-button>
          </Link>
        </div>
      )}

      {order?.status === "succeeded" && order.kind === "subscription" && (
        <div className="auth-card">
          <span className="auth-icon"><Icon name="ok" /></span>
          <h1 className="headline-small">Подписка оформлена</h1>
          <p className="body-medium">
            Действует до {user.subscription?.until ? new Date(user.subscription.until).toLocaleDateString("ru-RU") : "—"}:
            {" "}{user.subscription?.limit} автоисправлений в месяц. Спасибо!
          </p>
          <Link to="/vkr" className="link-btn">
            <md-filled-button><Icon name="fix" slot="icon" />Проверить работу</md-filled-button>
          </Link>
        </div>
      )}

      {order?.status === "succeeded" && order.kind === "autofix" && (
        <>
          <div className="banner banner-ok body-medium" role="status">
            <Icon name="ok" />
            <span>Оплата прошла, спасибо! {order.upload_id
              ? "Осталось нажать «Исправить и скачать»."
              : "Загрузите работу на странице проверки — исправление уже оплачено."}</span>
          </div>
          {order.upload_id ? (
            <AutoFix file={{ name: order.file_name || "работа.docx" }} uploadId={order.upload_id}
                     profileKey={order.profile || "vkr"} standards={order.standards.length ? order.standards : undefined} />
          ) : (
            <Link to="/vkr" className="link-btn">
              <md-filled-button><Icon name="fix" slot="icon" />Загрузить работу</md-filled-button>
            </Link>
          )}
        </>
      )}
    </section>
  );
}
