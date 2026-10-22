import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useProfiles } from "../ProfilesContext.jsx";
import { Icon } from "../ui.jsx";

const CARDS = [
  { key: "vkr", icon: "vkr", fallback: "Выпускная квалификационная работа" },
  { key: "coursework", icon: "coursework", fallback: "Курсовая работа" },
  { key: "standards", icon: "check", fallback: "Свой набор ГОСТов",
    text: "ГОСТ 7.32, ГОСТ Р 2.105 (ЕСКД), ГОСТ Р 7.0.11 (диссертации), списки литературы по 7.0.100 или 7.1 — " +
          "отметьте стандарты из своей методички." },
];

/** Тарифы: проверка бесплатно, разовое исправление и подписка. */
export function Pricing() {
  const { config } = useProfiles();
  const user = config.user;
  const [soon, setSoon] = useState(false);
  const price = config.autofix_price ?? 99;
  const subPrice = config.subscription_price ?? 249;
  const subLimit = config.subscription_limit ?? 100;
  return (
    <section className="pricing" aria-labelledby="pricing-title">
      <h2 id="pricing-title" className="headline-small">Тарифы</h2>
      <div className="price-grid">
        <div className="price-card">
          <span className="label-large muted">Проверка</span>
          <span className="price-value headline-medium">0&nbsp;₽</span>
          <p className="body-medium">Отчёт с номерами страниц и файл Word с отметками — без регистрации.</p>
        </div>
        <div className="price-card">
          <span className="label-large muted">Разовое исправление</span>
          <span className="price-value headline-medium">{price}&nbsp;₽</span>
          <p className="body-medium">Автоисправление одной работы: поля, шрифт, интервалы, заголовки, список источников.</p>
        </div>
        <div className="price-card featured">
          <span className="label-large">Подписка <span className="tag">выгодно</span></span>
          <span className="price-value headline-medium">{subPrice}&nbsp;₽<span className="body-medium"> / месяц</span></span>
          <p className="body-medium">
            {subLimit} автоисправлений в месяц — для тех, кто правит работу много раз, и для преподавателей.
          </p>
          {user ? (
            <md-filled-button onClick={() => (config.payments_enabled ? null : setSoon(true))}>
              <Icon name="fix" slot="icon" />
              Оформить подписку
            </md-filled-button>
          ) : (
            <Link to="/register" state={{ from: "/" }} className="link-btn">
              <md-filled-button>
                <Icon name="userAdd" slot="icon" />
                Зарегистрироваться
              </md-filled-button>
            </Link>
          )}
        </div>
      </div>
      {soon && (
        <div className="banner banner-info body-medium" role="status">
          <Icon name="info" />
          <span>Оплата подключается и заработает в ближайшие дни. Проверка и «Работа с отметками» уже бесплатны.</span>
        </div>
      )}
    </section>
  );
}

export default function Home({ notFound }) {
  const { profiles } = useProfiles();
  useEffect(() => {
    document.title = "Нормоконтроль онлайн — проверка оформления ВКР и курсовых по ГОСТ 7.32-2017";
  }, []);
  return (
    <section className="container page">
      {notFound && <div className="banner banner-error body-medium" role="alert"><Icon name="error" /> Страница не найдена. Выберите тип работы:</div>}
      <h1 className="display-small hero-title">Проверьте оформление работы раньше, чем это сделает нормоконтролёр</h1>
      <p className="body-large supporting">
        Выберите тип работы, загрузите .docx или .pdf — сервис сверит поля, шрифт, интервалы,
        заголовки, подписи и нумерацию страниц с ГОСТ&nbsp;7.32&#8209;2017 и покажет, где именно найдены отклонения.
      </p>
      <div className="card-grid">
        {CARDS.map(({ key, icon, fallback }) => {
          const p = profiles?.[key];
          return (
            <Link key={key} to={`/${key}`} className="card card-filled card-link">
              <md-ripple />
              <span className="card-icon"><Icon name={icon} /></span>
              <h2 className="title-large">{p?.title ?? fallback}</h2>
              <p className="body-medium">{p?.description ?? CARDS.find((c) => c.key === key).text ?? ""}</p>
              <span className="card-action label-large">Проверить <Icon name="forward" size={18} /></span>
            </Link>
          );
        })}
      </div>
      <Pricing />
      <Link to="/gost" className="list-link label-large home-gost">
        <Icon name="info" size={20} /> Требования ГОСТ 7.32-2017 к оформлению: поля, шрифт, заголовки, подписи
        <Icon name="forward" size={18} />
      </Link>
    </section>
  );
}
