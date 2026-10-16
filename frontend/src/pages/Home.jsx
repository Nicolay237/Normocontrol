import { Link } from "react-router-dom";
import { useProfiles } from "../ProfilesContext.jsx";

const ORDER = ["vkr", "coursework"];
const FALLBACK = { vkr: "Выпускная квалификационная работа", coursework: "Курсовая работа" };

export default function Home({ notFound }) {
  const { profiles } = useProfiles();
  return (
    <section className="home">
      {notFound && <p className="form-error">Страница не найдена. Выберите тип работы:</p>}
      <h1>Проверьте оформление работы раньше, чем это сделает нормоконтролёр</h1>
      <p className="hero-sub">
        Выберите тип работы, загрузите .docx или .pdf — сервис сверит поля, шрифт, интервалы,
        заголовки, подписи и нумерацию страниц с ГОСТ&nbsp;7.32&#8209;2017 и покажет, где именно найдены отклонения.
      </p>
      <div className="choice-grid">
        {ORDER.map((key) => {
          const p = profiles?.[key];
          return (
            <Link key={key} to={`/${key}`} className="choice-card">
              <h2>{p?.title ?? FALLBACK[key]}</h2>
              <p>{p?.description ?? ""}</p>
              <span className="choice-go">Проверить →</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
