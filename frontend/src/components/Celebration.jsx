import { useEffect, useRef } from "react";

/**
 * Праздник на весь экран, когда замечаний нет: две хлопушки из нижних углов и залп фейерверков.
 * Холст поверх страницы не перехватывает клики и сам убирается через несколько секунд.
 * Пользователям с «уменьшить движение» в настройках системы анимацию не показываем.
 *
 * Движение считается по реальному времени, а не по кадрам: на мониторе 120–144 Гц салют
 * идёт с той же скоростью, что и на 60 Гц. SPEED замедляет всё разом (1 — «как в жизни»).
 */

const PALETTE = ["#ff4d6d", "#ffd166", "#06d6a0", "#4cc9f0", "#f72585", "#ffffff", "#b388ff", "#ff9f1c"];
const GRAVITY = 0.12;
const SPEED = 0.55;     // общее замедление: конфетти планирует, искры гаснут неспешно
const DURATION = 9000;  // мс — потом холст исчезает
const FADE_FROM = 6800; // мс — с этого момента оставшееся конфетти тает

const rand = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

function themeColors() {
  const css = getComputedStyle(document.documentElement);
  const own = ["--md-sys-color-primary", "--md-sys-color-tertiary"]
    .map((v) => css.getPropertyValue(v).trim()).filter(Boolean);
  return [...PALETTE, ...own];
}

/** Конфетти из хлопушки: летит вверх веером, крутится, планирует и падает. */
function popper(x, y, dir, colors, count) {
  return Array.from({ length: count }, () => {
    const angle = (dir > 0 ? rand(-80, -45) : rand(-135, -100)) * (Math.PI / 180);
    const speed = rand(9, 19);
    return {
      kind: "confetti", x, y,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      w: rand(6, 11), h: rand(3, 6), rot: rand(0, Math.PI * 2), vr: rand(-0.3, 0.3),
      wobble: rand(0, Math.PI * 2), color: pick(colors), round: Math.random() < 0.25,
      life: 1, decay: rand(0.012, 0.02),
    };
  });
}

/** Ракета фейерверка: взлетает со следом, на вершине рассыпается искрами. */
function rocket(w, h, colors, delay) {
  // скорость под высоту взрыва: от 15 до 45% высоты экрана от верха
  const rise = h * rand(0.55, 0.85);
  return {
    kind: "rocket", x: rand(w * 0.2, w * 0.8), y: h + 10, vx: rand(-1, 1),
    vy: -Math.sqrt(2 * GRAVITY * 1.6 * rise), color: pick(colors), delay, trail: [],
  };
}

function burst(x, y, colors) {
  const color = pick(colors);
  const second = Math.random() < 0.5 ? pick(colors) : color;
  const n = 90;
  return Array.from({ length: n }, (_, i) => {
    const angle = (i / n) * Math.PI * 2 + rand(-0.05, 0.05);
    const speed = rand(2.5, 6.5);
    return {
      kind: "spark", x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      color: i % 3 ? color : second, life: 1, decay: rand(0.011, 0.018), r: rand(1.6, 2.6),
    };
  });
}

export default function Celebration({ onDone }) {
  const ref = useRef(null);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      onDone?.();
      return undefined;
    }
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const colors = themeColors();
    const small = w < 600; // на телефоне частиц меньше — анимация остаётся плавной
    let parts = [
      ...popper(0, h, +1, colors, small ? 70 : 140),
      ...popper(w, h, -1, colors, small ? 70 : 140),
    ];
    const rockets = Array.from({ length: small ? 4 : 6 }, (_, i) => rocket(w, h, colors, 400 + i * 750));
    const start = performance.now();
    let last = start;
    let frame;

    function draw(now) {
      const t = now - start;
      // шаг «в кадрах при 60 Гц»: одинаковая скорость на любом мониторе; после паузы вкладки — не рывок
      const dt = Math.min((now - last) / (1000 / 60), 3) * SPEED;
      last = now;
      ctx.clearRect(0, 0, w, h);

      for (const r of rockets) {
        if (r.done || t < r.delay) continue;
        r.trail.push([r.x, r.y]);
        if (r.trail.length > 14) r.trail.shift();
        r.x += r.vx * dt;
        r.y += r.vy * dt;
        r.vy += GRAVITY * 1.6 * dt;
        ctx.strokeStyle = r.color;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.8;
        ctx.beginPath();
        r.trail.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.stroke();
        if (r.vy >= -1) { // вершина — взрыв
          r.done = true;
          parts = parts.concat(burst(r.x, r.y, colors));
        }
      }

      for (const p of parts) {
        if (p.kind === "confetti") {
          const drag = 0.985 ** dt;
          p.vx *= drag;
          p.vy = p.vy * drag + GRAVITY * dt;
          p.wobble += 0.12 * dt;
          p.x += (p.vx + Math.sin(p.wobble) * 0.8) * dt;
          p.y += p.vy * dt;
          p.rot += p.vr * dt;
          if (t > FADE_FROM) p.life -= p.decay * dt;
          ctx.globalAlpha = Math.max(0, p.life);
          ctx.fillStyle = p.color;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          if (p.round) {
            ctx.beginPath();
            ctx.arc(0, 0, p.h, 0, Math.PI * 2);
            ctx.fill();
          } else {
            ctx.scale(1, Math.cos(p.wobble)); // «переворачивается» в полёте
            ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
          }
          ctx.restore();
        } else {
          const drag = 0.97 ** dt;
          p.vx *= drag;
          p.vy = p.vy * drag + GRAVITY * 0.6 * dt;
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          p.life -= p.decay * dt;
          ctx.globalAlpha = Math.max(0, p.life);
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      parts = parts.filter((p) => p.life > 0 && p.y < h + 40);

      if (t < DURATION) frame = requestAnimationFrame(draw);
      else onDone?.();
    }
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <canvas ref={ref} className="celebration" aria-hidden="true" />;
}
