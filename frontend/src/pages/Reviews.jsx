import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchReviews, sendReview } from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr } from "../ui.jsx";

const fmtDate = (iso) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
const RATING_WORDS = ["", "Плохо", "Так себе", "Нормально", "Хорошо", "Отлично"];
const SOURCES = { check: "проверки", fix: "исправления" };
const EMOJI = [
  "😀", "😊", "😍", "🤩", "😎", "🥳", "😅", "😂", "🙂", "😉", "🤔", "😐",
  "😕", "😢", "😭", "😡", "😱", "🤯", "😌", "😴", "👍", "👎", "👌", "👏",
  "🙏", "💪", "🔥", "✨", "⭐", "❤️", "💯", "✅", "❌", "📄", "🎓", "📚",
];

/** Кнопка со смайликами: выбранный вставляется в место курсора. */
function EmojiPicker({ onPick }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (e.type === "keydown" ? e.key === "Escape" : !ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [open]);
  return (
    <span className="emoji" ref={ref}>
      <button type="button" className="icon-btn" title="Смайлики" aria-label="Смайлики" aria-expanded={open}
              onClick={() => setOpen(!open)}>
        <Icon name="smile" size={22} />
      </button>
      {open && (
        <span className="emoji-pop" role="listbox" aria-label="Смайлики">
          {EMOJI.map((em) => (
            <button key={em} type="button" role="option" aria-selected="false"
                    onMouseDown={(e) => e.preventDefault()} onClick={() => onPick(em)}>{em}</button>
          ))}
        </span>
      )}
    </span>
  );
}

/** Звёзды оценки: только показ или выбор (onChange). */
export function Stars({ value, onChange, size = 20 }) {
  const [hover, setHover] = useState(0);
  if (!onChange)
    return (
      <span className="stars" role="img" aria-label={`${value} из 5`}>
        {[1, 2, 3, 4, 5].map((n) => <Icon key={n} name="star" size={size} className={n <= Math.round(value) ? "on" : ""} />)}
      </span>
    );
  const shown = hover || value;
  return (
    <span className="stars stars-input" role="radiogroup" aria-label="Оценка" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} из 5`}
                className={n <= shown ? "on" : ""} onMouseEnter={() => setHover(n)} onClick={() => onChange(n)}>
          <Icon name="star" size={size} />
        </button>
      ))}
      <span className="label-large stars-word">{RATING_WORDS[shown]}</span>
    </span>
  );
}

function ReviewForm({ source, onSent }) {
  const { user } = useSession();
  const [form, setForm] = useState({ rating: 0, name: "", text: "", website: "" });
  const [state, setState] = useState({ busy: false, error: null });
  const ref = useRef(null);
  const textRef = useRef(null);

  /** Смайлик — туда, где стоит курсор (или в конец), курсор — сразу после него. */
  function insertEmoji(em) {
    const ta = textRef.current;
    const start = ta?.selectionStart ?? form.text.length, end = ta?.selectionEnd ?? form.text.length;
    const text = form.text.slice(0, start) + em + form.text.slice(end);
    if (text.length > 2000) return;
    setForm({ ...form, text });
    requestAnimationFrame(() => { ta?.focus(); ta?.setSelectionRange(start + em.length, start + em.length); });
  }

  useEffect(() => { if (user?.name && !form.name) setForm((f) => ({ ...f, name: user.name.split(" ")[0] })); }, [user]);
  // пришли по кнопке после проверки или исправления — сразу к форме
  useEffect(() => { if (source) ref.current?.scrollIntoView({ block: "center" }); }, [source]);

  async function submit(e) {
    e.preventDefault();
    if (!form.rating) return setState({ busy: false, error: "Поставьте оценку — нажмите на звезду." });
    setState({ busy: true, error: null });
    try {
      await sendReview({ ...form, source });
      onSent();
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  const len = form.text.trim().length;
  return (
    <form ref={ref} id="review-form" className="panel form review-form" onSubmit={submit}>
      <h2 className="title-large">
        {source ? `Как вам результат ${SOURCES[source]}?` : "Оставить отзыв"}
      </h2>
      <Stars value={form.rating} onChange={(rating) => setForm({ ...form, rating })} size={32} />
      <label className="field">
        <span className="field-label label-large">Отзыв</span>
        <span className="review-input">
        <textarea ref={textRef} className="field-input body-large" rows={5} maxLength={2000} required value={form.text}
                  placeholder="Что понравилось, что нашёл сервис, чего не хватило"
                  onChange={(e) => setForm({ ...form, text: e.target.value })} />
        <EmojiPicker onPick={insertEmoji} />
        </span>
        <span className="field-hint body-medium">{len > 0 && len < 10 ? `Ещё хотя бы ${10 - len} симв.` : " "}</span>
      </label>
      <Field label="Имя (необязательно)" value={form.name} maxLength={80} autoComplete="given-name"
             hint="Будет показано рядом с отзывом. Если пусто — подпишем «Аноним»."
             onChange={(e) => setForm({ ...form, name: e.target.value })} />
      {/* ловушка для ботов: человек это поле не видит */}
      <input className="hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={form.website}
             onChange={(e) => setForm({ ...form, website: e.target.value })} />
      {state.error && (
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
      )}
      <md-filled-button type="submit" disabled={attr(state.busy)}>
        <Icon name="send" slot="icon" />
        {state.busy ? "Отправляем…" : "Отправить отзыв"}
      </md-filled-button>
      <p className="body-small muted">
        Отзыв появится на странице после проверки модератором. Отправляя его, вы соглашаетесь с{" "}
        <Link to="/privacy">политикой обработки персональных данных</Link>.
      </p>
    </form>
  );
}

export default function Reviews() {
  const [params] = useSearchParams();
  const source = ["check", "fix"].includes(params.get("from")) ? params.get("from") : null;
  const [data, setData] = useState(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    document.title = "Отзывы — Нормоконтроль";
    fetchReviews().then(setData).catch(() => setData({ items: [], count: 0, average: null }));
  }, []);

  return (
    <section className="container page reviews-page">
      <p className="label-large eyebrow">Отзывы</p>
      <h1 className="display-small hero-title">Что говорят о сервисе</h1>
      <p className="body-large supporting">
        Проверяли или исправляли работу? Расскажите, как всё прошло, — это помогает другим студентам
        и нам сделать проверку точнее.
      </p>

      {data?.count > 0 && (
        <div className="reviews-summary">
          <span className="display-small">{String(data.average).replace(".", ",")}</span>
          <div>
            <Stars value={data.average} size={24} />
            <div className="body-medium muted">{data.count} {plural(data.count)}</div>
          </div>
        </div>
      )}

      {sent ? (
        <div className="banner banner-ok body-medium" role="status">
          <Icon name="ok" />
          <span><b>Спасибо за отзыв!</b> Он появится здесь после проверки модератором.</span>
        </div>
      ) : (
        <ReviewForm source={source} onSent={() => { setSent(true); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
      )}

      {!data && <div className="loading"><md-circular-progress indeterminate="" /></div>}
      {data && (data.items.length ? (
        <ul className="review-list">
          {data.items.map((r) => (
            <li key={r.id} className="review">
              <div className="review-head">
                <span className="title-medium">{r.name}</span>
                <Stars value={r.rating} size={18} />
              </div>
              <p className="body-large review-text">{r.text}</p>
              <span className="label-medium muted">{fmtDate(r.date)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="body-medium muted reviews-empty">Отзывов пока нет — ваш может стать первым.</p>
      ))}
    </section>
  );
}

function plural(n) {
  if (n % 10 === 1 && n % 100 !== 11) return "отзыв";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "отзыва";
  return "отзывов";
}
