import { useEffect, useMemo, useState } from "react";
import { checkFile, fetchStandards } from "../api.js";
import UploadForm from "../components/UploadForm.jsx";
import ReportView from "../components/ReportView.jsx";
import AutoFix from "../components/AutoFix.jsx";
import Progress from "../components/Progress.jsx";
import { Icon } from "../ui.jsx";

const IDLE = { phase: "idle", report: null, error: null, file: null, upload: null };
const STORAGE_KEY = "normocontrol.standards";

function loadSaved() {
  try {
    const v = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

function save(keys) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(keys)); } catch { /* приватный режим */ }
}

// результат живёт, пока открыта вкладка (как на страницах ВКР и курсовых)
let lastResult = null;

/**
 * Раздел «Выбор ГОСТов»: пользователь отмечает стандарты сам. В группах «Оформление текста»
 * и «Список источников» стандарты противоречат друг другу — пока выбран один, остальные недоступны.
 */
export default function StandardsPage() {
  const [catalog, setCatalog] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selected, setSelected] = useState(() => loadSaved());
  const [state, setStateRaw] = useState(() => lastResult || IDLE);

  const setState = (next) => setStateRaw((prev) => {
    const value = typeof next === "function" ? next(prev) : next;
    lastResult = value.phase === "done" ? value : null;
    return value;
  });

  useEffect(() => {
    document.title = "Проверка по выбранным ГОСТам — Нормоконтроль";
    fetchStandards()
      .then((c) => {
        setCatalog(c);
        // сохранённый выбор мог устареть — оставляем только существующие стандарты
        setSelected((s) => {
          const known = new Set(c.standards.map((x) => x.key));
          const kept = (s || c.default).filter((k) => known.has(k));
          return kept.length ? kept : c.default;
        });
      })
      .catch((e) => setLoadError(e.message));
  }, []);

  const byKey = useMemo(() => Object.fromEntries((catalog?.standards || []).map((s) => [s.key, s])), [catalog]);

  function toggle(std) {
    setSelected((cur) => {
      const next = cur.includes(std.key) ? cur.filter((k) => k !== std.key) : [...cur, std.key];
      save(next);
      return next;
    });
  }

  // стандарт той же исключающей группы, который уже выбран (из-за него этот недоступен)
  function blockedBy(std) {
    const group = catalog.groups.find((g) => g.key === std.group);
    if (!group?.exclusive || selected.includes(std.key)) return null;
    const other = selected.find((k) => byKey[k]?.group === std.group);
    return other ? byKey[other] : null;
  }

  async function onSubmit(file) {
    setState({ phase: "loading", report: null, error: null, file, upload: 0 });
    try {
      const report = await checkFile(file, "custom", (upload) => setState((s) => ({ ...s, upload })), selected);
      setState({ phase: "done", report, error: null, file, upload: null });
      window.scrollTo({ top: 0 });
    } catch (e) {
      setState({ ...IDLE, error: e.message });
    }
  }

  if (state.phase === "done") {
    const r = state.report;
    return (
      <section className="container page">
        <ReportView key={r.report_id} report={r}>
          {!r.clean && (r.autofix_supported ? (
            <AutoFix file={state.file} uploadId={r.upload_id} profileKey="custom" standards={r.standards}
                     total={r.total} fixable={r.fixable || 0} />
          ) : r.upload_id && (
            <div className="banner banner-info body-medium">
              <Icon name="info" />
              <span>
                Автоисправление пока умеет оформление по ГОСТ 7.32-2017 и список источников по ГОСТ Р 7.0.100-2018.
                Для этого набора стандартов используйте «Работу с отметками» — все замечания будут прямо в файле.
              </span>
            </div>
          ))}
        </ReportView>
        <div className="reset">
          <md-text-button onClick={() => setState(IDLE)}>
            <Icon name="back" slot="icon" />
            Проверить другой файл
          </md-text-button>
        </div>
      </section>
    );
  }

  return (
    <section className="container page">
      <header className="hero">
        <span className="hero-art" aria-hidden="true"><Icon name="check" size={176} /></span>
        <span className="hero-badge label-large"><Icon name="check" size={18} /> Свой набор стандартов</span>
        <h1 className="display-small hero-heading">Проверка по выбранным ГОСТам</h1>
        <p className="body-large hero-tagline">
          Отметьте стандарты из своей методички — проверим работу только по ним.
        </p>
      </header>

      {loadError && <div className="banner banner-error body-medium" role="alert"><Icon name="error" /> {loadError}</div>}
      {!catalog && !loadError && <div className="loading"><md-circular-progress indeterminate="" /></div>}

      {catalog && selected && (
        <div className="std-groups">
          {catalog.groups.map((g) => (
            <fieldset key={g.key} className="std-group">
              <legend className="title-medium">{g.title}</legend>
              <p className="body-medium muted">{g.hint}</p>
              <div className="std-list">
                {catalog.standards.filter((s) => s.group === g.key).map((s) => {
                  const on = selected.includes(s.key);
                  const blocker = blockedBy(s);
                  return (
                    <label key={s.key} className={`std-card${on ? " on" : ""}${blocker ? " blocked" : ""}`}>
                      <input type="checkbox" checked={on} disabled={!!blocker} onChange={() => toggle(s)} />
                      <span className="std-check" aria-hidden="true">{on && <Icon name="tick" size={16} />}</span>
                      <span className="std-text">
                        <span className="title-small std-code">{s.code}</span>
                        <span className="body-medium">{s.title}</span>
                        <span className="body-small muted">{s.about}</span>
                        {blocker && (
                          <span className="label-medium std-blocked">
                            <Icon name="lock" size={14} /> Нельзя вместе с {blocker.code} — снимите его, чтобы выбрать этот
                          </span>
                        )}
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </div>
      )}

      {catalog && selected && (selected.length === 0 ? (
        <div className="banner banner-error body-medium" role="alert">
          <Icon name="error" /> Выберите хотя бы один стандарт.
        </div>
      ) : state.phase === "loading" ? (
        <Progress upload={state.upload} workingText="Проверяем по выбранным ГОСТам…"
                  hint="Обычно несколько секунд, большие работы — до минуты." />
      ) : (
        <UploadForm onSubmit={onSubmit} serverError={state.error} />
      ))}
    </section>
  );
}
