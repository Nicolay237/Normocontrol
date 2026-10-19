import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useProfiles } from "../ProfilesContext.jsx";
import { Icon } from "../ui.jsx";
import { plural } from "./ReportView.jsx";

const BENEFITS = [
  "Поля, шрифт, интервалы, отступы, заголовки, подписи и нумерация — по ГОСТ",
  "Текст работы не меняется — правится только оформление",
  "Готовый .docx сразу после оплаты, исходный файл остаётся у вас",
  "Что нельзя исправить автоматически — списком с номерами страниц",
];

/**
 * Предложение автоисправления для пользователей без входа: сколько замечаний уйдёт, цена и кнопка.
 * Пока оплата не подключена (payments_enabled = false), кнопка объясняет, что оплата скоро
 * заработает, и предлагает бесплатную «работу с отметками».
 */
export default function Offer({ total, fixable }) {
  const { config } = useProfiles();
  const location = useLocation();
  const [soon, setSoon] = useState(false);
  const price = config.autofix_price ?? 149;
  const left = Math.max(0, total - fixable);

  return (
    <section className="offer">
      <span className="offer-art" aria-hidden="true"><Icon name="fix" size={160} /></span>
      <div className="offer-top">
        <span className="hero-badge label-large"><Icon name="fix" size={18} /> Автоисправление</span>
        <span className="price title-large">{price}&nbsp;₽</span>
      </div>

      <h2 className="headline-small offer-title">
        {fixable > 0
          ? <>Исправим до {fixable} {plural(fixable)} из {total} за пару секунд</>
          : <>Исправим оформление за пару секунд</>}
      </h2>

      {fixable > 0 && (
        <div className="before-after" aria-label={`Сейчас ${total}, после исправления — ${left <= 5 ? "единицы" : `около ${left}`}`}>
          <div><span className="ba-num bad">{total}</span><span className="label-medium">сейчас</span></div>
          <Icon name="forward" size={28} />
          {/* оценка до запуска исправления: точное число не обещаем, когда остаток мал */}
          <div><span className="ba-num ok">{left <= 5 ? "единицы" : `≈ ${left}`}</span><span className="label-medium">после исправления</span></div>
        </div>
      )}

      <ul className="benefits body-medium">
        {BENEFITS.map((b) => <li key={b}><Icon name="tick" size={18} /><span>{b}</span></li>)}
      </ul>

      <div className="offer-cta">
        <md-filled-button
          class="buy"
          onClick={() => (config.payments_enabled ? null : setSoon(true))}
        >
          <Icon name="fix" slot="icon" />
          Исправить за {price}&nbsp;₽
        </md-filled-button>
        <span className="label-medium muted">Разовая оплата · без регистрации · карта или СБП</span>
      </div>

      {soon && (
        <div className="banner banner-info body-medium" role="status">
          <Icon name="info" />
          <span>
            Оплата подключается и заработает в ближайшие дни. А пока бесплатно доступна
            <b> «Работа с отметками»</b> выше — все ошибки отмечены прямо в вашем файле.
          </span>
        </div>
      )}

      <p className="body-medium offer-uni">
        Вы из университета?{" "}
        <Link to="/login" state={{ from: location.pathname }}>Войдите</Link> — для вас бесплатно.
      </p>
    </section>
  );
}
