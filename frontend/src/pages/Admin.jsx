import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import {
  adminBulk, adminCreate, adminDelete, adminPackSettings, adminPacks, adminReset, adminUpdate, adminUsers,
} from "../api.js";
import { useSession } from "../ProfilesContext.jsx";
import { Field, Icon, attr, submitOnEnter } from "../ui.jsx";

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("ru-RU") : "—");

/** Выданные логины/пароли: показываются один раз, их можно скопировать или скачать CSV. */
function Credentials({ items, onClose }) {
  const text = items.map((c) => `${c.name}\t${c.login}\t${c.password}`).join("\n");
  const csv = "﻿ФИО;Логин;Пароль\n" + items.map((c) => [c.name, c.login, c.password].map((v) => `"${v.replace(/"/g, '""')}"`).join(";")).join("\n");
  const href = useMemo(() => URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })), [csv]);
  useEffect(() => () => URL.revokeObjectURL(href), [href]);
  const [copied, setCopied] = useState(false);

  return (
    <section className="creds" role="status">
      <div className="creds-head">
        <Icon name="key" />
        <div>
          <h2 className="title-medium">Выданные пароли ({items.length})</h2>
          <p className="body-medium muted">
            Сохраните их сейчас — повторно пароль увидеть нельзя, только сбросить. При первом входе пользователь задаст свой.
          </p>
        </div>
      </div>
      <ul className="creds-list">
        {items.map((c) => (
          <li key={c.login}>
            <span className="body-medium">{c.name}</span>
            <code className="label-large">{c.login}</code>
            <code className="label-large">{c.password}</code>
          </li>
        ))}
      </ul>
      <div className="row-actions">
        <md-filled-tonal-button onClick={() => navigator.clipboard?.writeText(text).then(() => setCopied(true))}>
          <Icon name="copy" slot="icon" />
          {copied ? "Скопировано" : "Копировать"}
        </md-filled-tonal-button>
        <md-outlined-button href={href} download="normocontrol_logins.csv">
          <Icon name="download" slot="icon" />
          Скачать CSV
        </md-outlined-button>
        <md-text-button onClick={onClose}>Готово</md-text-button>
      </div>
    </section>
  );
}

/** Дополнительная проверка вуза: описание, сколько людей с доступом и настройки (JSON). */
function PackCard({ pack, onSaved }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => JSON.stringify(pack.settings, null, 2));
  const [state, setState] = useState({ busy: false, error: null, saved: false });
  useEffect(() => setText(JSON.stringify(pack.settings, null, 2)), [pack]);

  async function save(settings) {
    setState({ busy: true, error: null, saved: false });
    try {
      const value = settings === undefined ? JSON.parse(text) : settings;
      onSaved((await adminPackSettings(pack.key, value)).pack);
      setState({ busy: false, error: null, saved: true });
    } catch (e) {
      const msg = e instanceof SyntaxError ? "Это не JSON: проверьте кавычки и запятые." : e.message;
      setState({ busy: false, error: msg, saved: false });
    }
  }

  return (
    <li className="pack-card">
      <div className="pack-head">
        <Icon name="check" />
        <div>
          <h3 className="title-medium">{pack.title}</h3>
          <p className="body-medium muted">{pack.description}</p>
          <p className="label-medium muted">
            Включена у {pack.users} · только для ВКР{pack.customized && " · настройки изменены"}
          </p>
        </div>
        <md-text-button onClick={() => setOpen(!open)}>
          <Icon name="settings" slot="icon" />
          {open ? "Скрыть" : "Настройки"}
        </md-text-button>
      </div>
      {open && (
        <div className="pack-settings">
          <textarea className="field-input code body-medium" rows={14} spellCheck={false} value={text}
                    aria-label={`Настройки: ${pack.title}`}
                    onChange={(e) => { setText(e.target.value); setState({ ...state, saved: false }); }} />
          {state.error && (
            <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{state.error}</span></div>
          )}
          {state.saved && (
            <div className="banner banner-ok body-medium" role="status"><Icon name="ok" /><span>Сохранено — действует со следующей проверки.</span></div>
          )}
          <div className="row-actions">
            <md-filled-tonal-button onClick={() => save()} disabled={attr(state.busy)}>
              <Icon name="ok" slot="icon" />
              Сохранить
            </md-filled-tonal-button>
            {pack.customized && (
              <md-text-button onClick={() => window.confirm("Вернуть настройки по умолчанию?") && save(null)}>
                <Icon name="reset" slot="icon" />
                По умолчанию
              </md-text-button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function UserRow({ u, me, packs, onChanged, onCredentials }) {
  const [busy, setBusy] = useState(false);
  async function act(fn, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    try { await fn(); } catch (e) { window.alert(e.message); } finally { setBusy(false); }
  }
  const self = u.id === me.id;
  const subActive = u.subscription_until && new Date(u.subscription_until) > new Date();
  return (
    <li className={`user-row${u.active ? "" : " inactive"}`}>
      <div className="user-main">
        <span className="title-medium">{u.name}</span>
        <span className="body-medium muted">
          <code>{u.login}</code>
          {u.role === "admin" && <span className="tag">администратор</span>}
          {!u.active && <span className="tag tag-error">заблокирован</span>}
          {u.active && u.must_change_password && <span className="tag">ждёт первого входа</span>}
          {u.registered && <span className="tag">регистрация</span>}
          {u.free_autofix && u.role !== "admin" && <span className="tag tag-ok">бесплатно</span>}
          {subActive && <span className="tag tag-ok">подписка до {fmtDate(u.subscription_until)}</span>}
        </span>
        <span className="label-medium muted">последний вход: {fmtDate(u.last_login_at)}</span>
        {u.role !== "admin" && !u.free_autofix && (
          <span className="pack-toggles">
            <button type="button" className="pack-toggle label-medium" disabled={busy}
                    title={subActive ? "Продлить подписку на 30 дней" : "Выдать подписку на 30 дней"}
                    onClick={() => act(async () => { await adminUpdate(u.id, { subscription_days: 30 }); onChanged(); })}>
              <Icon name="plus" size={16} /> Подписка 30 дней
            </button>
            {subActive && (
              <button type="button" className="pack-toggle label-medium" disabled={busy}
                      onClick={() => act(async () => { await adminUpdate(u.id, { subscription_cancel: true }); onChanged(); },
                                         `Отменить подписку для ${u.name}?`)}>
                <Icon name="block" size={16} /> Отменить подписку
              </button>
            )}
          </span>
        )}
        {packs.length > 0 && (
          <span className="pack-toggles">
            {packs.map((p) => {
              const on = u.packs.includes(p.key);
              return (
                <button key={p.key} type="button" className={`pack-toggle label-medium${on ? " on" : ""}`}
                        aria-pressed={on} disabled={busy}
                        title={on ? `Выключить: ${p.title}` : `Включить: ${p.title}`}
                        onClick={() => act(async () => {
                          const next = on ? u.packs.filter((k) => k !== p.key) : [...u.packs, p.key];
                          await adminUpdate(u.id, { packs: next });
                          onChanged();
                        })}>
                  <Icon name={on ? "tick" : "plus"} size={16} /> Проверка {p.short}
                </button>
              );
            })}
          </span>
        )}
      </div>
      <div className="user-actions">
        {u.role !== "admin" && (
          <button className={`icon-btn${u.free_autofix ? " on" : ""}`} disabled={busy}
                  title={u.free_autofix ? "Закрыть бесплатное исправление" : "Открыть бесплатное исправление"}
                  aria-label={`${u.free_autofix ? "Закрыть" : "Открыть"} бесплатное исправление для ${u.login}`}
                  aria-pressed={u.free_autofix}
                  onClick={() => act(async () => { await adminUpdate(u.id, { free_autofix: !u.free_autofix }); onChanged(); })}>
            <Icon name="gift" size={20} />
          </button>
        )}
        <button className="icon-btn" title="Сбросить пароль" aria-label={`Сбросить пароль ${u.login}`} disabled={busy}
                onClick={() => act(async () => onCredentials((await adminReset(u.id)).created),
                                   `Сбросить пароль для ${u.name}? Старый перестанет работать.`)}>
          <Icon name="reset" size={20} />
        </button>
        {!self && (
          <button className="icon-btn" title={u.active ? "Заблокировать" : "Разблокировать"} disabled={busy}
                  aria-label={`${u.active ? "Заблокировать" : "Разблокировать"} ${u.login}`}
                  onClick={() => act(async () => { await adminUpdate(u.id, { active: !u.active }); onChanged(); })}>
            <Icon name={u.active ? "block" : "lock"} size={20} />
          </button>
        )}
        {!self && (
          <button className="icon-btn danger" title="Удалить" aria-label={`Удалить ${u.login}`} disabled={busy}
                  onClick={() => act(async () => { await adminDelete(u.id); onChanged(); },
                                     `Удалить учётную запись ${u.name}? Это нельзя отменить.`)}>
            <Icon name="trash" size={20} />
          </button>
        )}
      </div>
    </li>
  );
}

export default function Admin() {
  const { user } = useSession();
  const [list, setList] = useState({ users: null, ephemeral: false, error: null });
  const [mode, setMode] = useState("one"); // one | bulk
  const [one, setOne] = useState({ name: "", login: "", role: "user" });
  const [bulk, setBulk] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);
  const [creds, setCreds] = useState(null);
  const [q, setQ] = useState("");
  const [packs, setPacks] = useState([]);

  const load = () => adminUsers()
    .then((r) => setList({ users: r.users, ephemeral: r.db_ephemeral, legalMissing: r.legal_missing, error: null }))
    .catch((e) => setList({ users: null, ephemeral: false, error: e.message }));

  const loadPacks = () => adminPacks().then((r) => setPacks(r.packs)).catch(() => setPacks([]));

  useEffect(() => {
    document.title = "Учётные записи — Нормоконтроль";
    if (user?.role === "admin") { load(); loadPacks(); }
  }, [user]);

  if (!user) return <Navigate to="/login" replace state={{ from: "/admin" }} />;
  if (user.role !== "admin") return <Navigate to="/account" replace />;

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const res = mode === "one"
        ? await adminCreate({ name: one.name, login: one.login || undefined, role: one.role })
        : await adminBulk(bulk.split("\n"));
      setCreds(res.created);
      setOne({ name: "", login: "", role: "user" });
      setBulk("");
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const filtered = (list.users || []).filter((u) =>
    !q || `${u.name} ${u.login}`.toLowerCase().includes(q.trim().toLowerCase()));
  const bulkCount = bulk.split("\n").filter((s) => s.trim()).length;

  return (
    <section className="container page">
      <p className="label-large eyebrow">Администрирование</p>
      <h1 className="display-small hero-title">Учётные записи</h1>
      <p className="body-large supporting">
        Выдайте логины сотрудникам университета — им сразу доступно бесплатное автоисправление. Тем, кто
        зарегистрировался сам, бесплатный доступ открывается кнопкой с подарком в списке.
      </p>

      {list.ephemeral && (
        <div className="banner banner-error body-medium" role="alert">
          <Icon name="error" />
          <span>База данных не подключена: учётные записи пропадут при следующем деплое. Задайте DATABASE_URL в переменных приложения на хостинге.</span>
        </div>
      )}

      {list.legalMissing?.length > 0 && (
        <div className="banner banner-error body-medium" role="alert">
          <Icon name="error" />
          <span>
            В оферте и на странице «Контакты» не заполнено: {list.legalMissing.join(", ")}. Задайте LEGAL_NAME,
            LEGAL_INN и CONTACT_EMAIL в .env на сервере — без реквизитов платёжный сервис не подключат.
          </span>
        </div>
      )}

      {creds && <Credentials items={creds} onClose={() => setCreds(null)} />}

      <form className="panel form" onSubmit={create} onKeyDown={submitOnEnter}>
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "one"} className={mode === "one" ? "on" : ""}
                  onClick={() => setMode("one")}><Icon name="userAdd" size={18} /> Один человек</button>
          <button type="button" role="tab" aria-selected={mode === "bulk"} className={mode === "bulk" ? "on" : ""}
                  onClick={() => setMode("bulk")}><Icon name="users" size={18} /> Группа списком</button>
        </div>

        {mode === "one" ? (
          <div className="form-grid">
            <Field label="ФИО" required value={one.name} placeholder="Иванов Иван Петрович"
                   onChange={(e) => setOne({ ...one, name: e.target.value })} />
            <Field label="Логин (необязательно)" value={one.login} autoCapitalize="none" spellCheck={false}
                   hint="Если пусто — придумаем из ФИО: ivanov.ip"
                   onChange={(e) => setOne({ ...one, login: e.target.value })} />
            <label className="check body-medium">
              <input type="checkbox" checked={one.role === "admin"}
                     onChange={(e) => setOne({ ...one, role: e.target.checked ? "admin" : "user" })} />
              Администратор (может выдавать учётки)
            </label>
          </div>
        ) : (
          <label className="field">
            <span className="field-label label-large">ФИО, по одному на строку</span>
            <textarea className="field-input body-large" rows={6} value={bulk}
                      placeholder={"Иванов Иван Петрович\nПетрова Мария Сергеевна"}
                      onChange={(e) => setBulk(e.target.value)} />
            <span className="field-hint body-medium">
              Логины придумаем из ФИО, пароли — случайные. {bulkCount > 0 && `Будет создано: ${bulkCount}.`}
            </span>
          </label>
        )}

        {formError && (
          <div className="banner banner-error body-medium" role="alert"><Icon name="error" /><span>{formError}</span></div>
        )}
        <md-filled-button type="submit" disabled={attr(busy || (mode === "bulk" ? !bulkCount : !one.name.trim()))}>
          <Icon name="userAdd" slot="icon" />
          {busy ? "Создаём…" : mode === "one" ? "Создать и выдать пароль" : `Создать ${bulkCount || ""}`}
        </md-filled-button>
      </form>

      <div className="list-head">
        <h2 className="title-large">Пользователи {list.users && <span className="muted">({list.users.length})</span>}</h2>
        <label className="search">
          <Icon name="search" size={20} />
          <input className="body-large" type="search" placeholder="Поиск по ФИО или логину" value={q}
                 onChange={(e) => setQ(e.target.value)} aria-label="Поиск" />
        </label>
      </div>
      {list.error && <div className="banner banner-error body-medium"><Icon name="error" /><span>{list.error}</span></div>}
      {!list.users && !list.error && <div className="loading"><md-circular-progress indeterminate="" /></div>}
      {list.users && (
        <ul className="user-list">
          {filtered.map((u) => (
            <UserRow key={u.id} u={u} me={user} packs={packs} onChanged={() => { load(); loadPacks(); }}
                     onCredentials={setCreds} />
          ))}
          {!filtered.length && <li className="body-medium muted empty">Никого не нашли.</li>}
        </ul>
      )}

      {packs.length > 0 && (
        <>
          <div className="list-head">
            <h2 className="title-large">Дополнительные проверки</h2>
          </div>
          <p className="body-medium muted supporting">
            Требования вуза сверх ГОСТ. Включаются каждому пользователю отдельно — кнопкой «Проверка …» в списке выше.
          </p>
          <ul className="pack-list">
            {packs.map((p) => (
              <PackCard key={p.key} pack={p}
                        onSaved={(next) => setPacks((all) => all.map((x) => (x.key === next.key ? next : x)))} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
