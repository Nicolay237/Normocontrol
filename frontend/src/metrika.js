/**
 * Яндекс.Метрика: посещения, переходы внутри сайта и цели воронки
 * (проверка → «Исправить» → оплата). Работает только на боевом домене —
 * локальная разработка и тесты статистику не засоряют.
 *
 * Цели (идентификаторы для «Цели → JavaScript-событие» в Метрике):
 *   check_done      получен отчёт проверки
 *   buy_click       нажали «Купить» (разовое исправление или подписку)
 *   autofix_done    получен исправленный файл
 *   register        зарегистрировались
 *   order_autofix   перешли к оплате разового исправления
 *   order_sub       перешли к оплате подписки
 *   paid            оплата подтверждена (с суммой)
 */

const COUNTER = 113833729;
const ON = typeof window !== "undefined" && window.location.hostname === "normocontrol.site";

let lastUrl = null;

function ym(...args) {
  if (ON && typeof window.ym === "function") window.ym(COUNTER, ...args);
}

if (ON) {
  // официальный код счётчика: очередь вызовов до загрузки tag.js
  window.ym = window.ym || function (...a) { (window.ym.a = window.ym.a || []).push(a); };
  window.ym.l = Date.now();
  const s = document.createElement("script");
  s.async = true;
  s.src = "https://mc.yandex.ru/metrika/tag.js";
  document.head.appendChild(s);
  window.ym(COUNTER, "init", {
    defer: true,              // просмотры отправляем сами — сайт одностраничный
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true,
  });
}

/** Просмотр страницы — при каждом переходе внутри сайта. */
export function hit(path) {
  const url = window.location.origin + path;
  if (url === lastUrl) return;
  ym("hit", url, { title: document.title, referer: lastUrl || document.referrer });
  lastUrl = url;
}

/** Достигнута цель воронки. */
export function goal(name, params) {
  ym("reachGoal", name, params);
}
