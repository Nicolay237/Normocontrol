import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { fetchOrder, uploadReport } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import AutoFix from "../components/AutoFix.jsx";
import ReportView from "../components/ReportView.jsx";
import { Icon } from "../ui.jsx";

const POLL_MS = 2500;
const POLL_FOR_MS = 5 * 60 * 1000; // СБП и 3-D Secure иногда подтверждаются не сразу

const PROFILE_PATH = { vkr: "/vkr", coursework: "/coursework", custom: "/standards" };

/** Карточка по центру — для ожидания, отмены и подписки. */
function Notice({ icon, title, children }) {
  return (
    <div className="auth-card pay-notice">
      <span className="auth-icon"><Icon name={icon} /></span>
      <h1 className="headline-small">{title}</h1>
      {children}
    </div>
  );
}

/**
 * Сюда ЮKassa возвращает покупателя после оплаты. Ждём подтверждения, а для разового исправления
 * показываем ту же проверку, что была до оплаты (отчёт по загруженной работе), — с открытым
 * автоисправлением.
 */
export default function PayPage() {
  const { orderId } = useParams();
  const { user, autofixEnabled, setSession } = useSession();
  const [state, setState] = useState({ order: null, error: null, waited: 0 });
  const [report, setReport] = useState({ data: null, error: null });
  // нажали «Исправить» — исправление может потратить последнее оплаченное, но результат должен остаться
  const [fixing, setFixing] = useState(false);

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

  const { order, error } = state;
  const paidFix = order?.status === "succeeded" && order.kind === "autofix" && order.upload_id;

  // отчёт по работе, загруженной перед оплатой
  useEffect(() => {
    if (!paidFix || report.data || report.error) return;
    uploadReport(order.upload_id, order.profile || "vkr", order.standards)
      .then((data) => setReport({ data, error: null }))
      .catch((e) => setReport({ data: null, error: e.message }));
  }, [paidFix]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return <Navigate to="/login" replace state={{ from: `/pay/${orderId}` }} />;
  const back = PROFILE_PATH[order?.profile] || "/vkr";

  return (
    <section className="container page">
      {error && !order && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{error}</span></div>
      )}
      {!order && !error && <div className="loading"><md-circular-progress indeterminate="" /></div>}

      {order?.status === "pending" && (
        <Notice icon="info" title="Ждём подтверждения оплаты">
          <p className="body-medium muted">
            Обычно это занимает несколько секунд. Страница обновится сама — закрывать её не нужно.
            {state.waited >= POLL_FOR_MS && " Если вы не завершили оплату, вернитесь к работе и оформите заказ ещё раз."}
          </p>
          {state.waited < POLL_FOR_MS && <div className="loading"><md-circular-progress indeterminate="" /></div>}
        </Notice>
      )}

      {order?.status === "canceled" && (
        <Notice icon="error" title="Оплата не прошла">
          <p className="body-medium muted">
            Деньги не списаны. Можно вернуться к работе и попробовать ещё раз — например, другой картой или через СБП.
          </p>
          <Link to={back} className="link-btn">
            <md-filled-button><Icon name="back" slot="icon" />Вернуться к проверке</md-filled-button>
          </Link>
        </Notice>
      )}

      {order?.status === "succeeded" && order.kind === "subscription" && (
        <Notice icon="ok" title="Подписка оформлена">
          <p className="body-medium">
            Действует до {user.subscription?.until ? new Date(user.subscription.until).toLocaleDateString("ru-RU") : "—"}:
            {" "}{user.subscription?.limit} автоисправлений в месяц. Спасибо!
          </p>
          <Link to="/vkr" className="link-btn">
            <md-filled-button><Icon name="fix" slot="icon" />Проверить работу</md-filled-button>
          </Link>
        </Notice>
      )}

      {order?.status === "succeeded" && order.kind === "autofix" && (
        <>
          <div className="banner banner-ok body-medium" role="status">
            <Icon name="ok" />
            <span>
              <b>Оплата прошла, спасибо!</b>{" "}
              {fixing
                ? "Исправленный файл — ниже, в карточке «Исправлено»."
                : autofixEnabled
                ? (order.upload_id && !report.error
                  ? "Автоисправление открыто — нажмите «Исправить и скачать» ниже."
                  : "Загрузите работу на странице проверки и нажмите «Исправить» — исправление уже оплачено.")
                : "Оплаченное исправление уже использовано. Если не успели скачать файл — напишите нам на почту из раздела «Контакты», поможем."}
            </span>
          </div>

          {paidFix && !report.data && !report.error && (
            <div className="loading"><md-circular-progress indeterminate="" /></div>
          )}
          {report.error && (
            <div className="banner banner-info body-medium">
              <Icon name="info" /><span>{report.error}</span>
            </div>
          )}
          {report.data && (
            <ReportView key={report.data.report_id} report={report.data}>
              {!report.data.clean && (autofixEnabled || fixing) && (
                <div onClickCapture={() => setFixing(true)}>
                  <AutoFix file={{ name: order.file_name || report.data.file }} uploadId={order.upload_id}
                           profileKey={order.profile || "vkr"}
                           standards={order.standards.length ? order.standards : undefined}
                           total={report.data.total} fixable={report.data.fixable || 0} />
                </div>
              )}
            </ReportView>
          )}
          <div className="reset">
            <Link to={back} className="link-btn">
              <md-text-button><Icon name="back" slot="icon" />Проверить другой файл</md-text-button>
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
