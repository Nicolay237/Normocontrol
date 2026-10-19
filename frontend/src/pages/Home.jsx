import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useProfiles } from "../ProfilesContext.jsx";
import { Icon } from "../ui.jsx";

const CARDS = [
  { key: "vkr", icon: "vkr", fallback: "Выпускная квалификационная работа" },
  { key: "coursework", icon: "coursework", fallback: "Курсовая работа" },
];

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
              <p className="body-medium">{p?.description ?? ""}</p>
              <span className="card-action label-large">Проверить <Icon name="forward" size={18} /></span>
            </Link>
          );
        })}
      </div>
      <Link to="/gost" className="list-link label-large home-gost">
        <Icon name="info" size={20} /> Требования ГОСТ 7.32-2017 к оформлению: поля, шрифт, заголовки, подписи
        <Icon name="forward" size={18} />
      </Link>
    </section>
  );
}
