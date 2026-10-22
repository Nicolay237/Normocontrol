import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useProfiles } from "../ProfilesContext.jsx";
import { Icon } from "../ui.jsx";
import { plural } from "./ReportView.jsx";

const BENEFITS = [
  "Поля, шрифт, интервалы, отступы, заголовки, подписи, нумерация и список литературы — по ГОСТ",
  "Текст работы не меняется — правится только оформление",
  "Готовый .docx сразу после оплаты, исходный файл остаётся у вас",
  "Что нельзя исправить автоматически — списком с номерами страниц",
];

/**
 * Предложение автоисправления для тех, у кого нет бесплатного доступа (без входа или после регистрации): сколько замечаний уйдёт, цена и кнопка.
 * Пока оплата не подключена (payments_enabled = false), кнопка объясняет, что оплата скоро
 * заработает, и предлагает бесплатную «работу с отметками».
 */
export default function Offer({ total, fixable }) {
  const { config } = useProfiles();
  const user = config.user;
  const location = useLocation();
  const [soon, setSoon] = useState(false);
  const price = config.autofix_price ?? 99;
  const left = Math.max(0, total - fixable);

  return (
    <section className="offer">
      <span className="offer-art" aria-hidden="true"><Icon name="fix" size={160} /></span>
      <div className="offer-top">
        <span className="hero-badge label-large"><Icon name="fix" size={18} /> Автоисправление</span>
        <span className="price title-large">{price}&nbsp;₽</span>
      </div>

      <h2 className="headline-small offer-title">Исправим оформление за пару секунд</h2>

      {fixable > 0 && (
        // оценка до запуска исправления: точное число не обещаем, когда остаток мал
        <p className="body-medium muted offer-estimate">
          {left === 0
            ? `Все ${total} ${plural(total)} по оформлению исправятся автоматически.`
            : left <= 5
              ? `Из ${total} найденных ${total % 10 === 1 && total % 100 !== 11 ? "замечания" : "замечаний"} автоматически исправятся почти все — останутся единичные, их нужно будет поправить вручную.`
              : `Автоматически исправятся около ${fixable} из ${total} замечаний, остальные нужно будет поправить вручную.`}
        </p>
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
        {user
          ? <>Вы преподаватель? Сообщите администратору свой логин <b>{user.login}</b> — он откроет бесплатный доступ.</>
          : <>Вы преподаватель?{" "}
              <Link to="/login" state={{ from: location.pathname }}>Войдите</Link> — для вас бесплатно.</>}
      </p>
    </section>
  );
}
