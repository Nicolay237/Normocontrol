import { useEffect, useState } from "react";
import { useProfiles } from "../ProfilesContext.jsx";
import { checkFile } from "../api.js";
import UploadForm from "../components/UploadForm.jsx";
import NormsList from "../components/NormsList.jsx";
import ReportView from "../components/ReportView.jsx";
import AutoFix from "../components/AutoFix.jsx";
import { Icon } from "../ui.jsx";
import Progress from "../components/Progress.jsx";

const IDLE = { phase: "idle", report: null, error: null, file: null, upload: null };

// Последний результат по каждому типу работы живёт, пока открыта вкладка: можно уйти
// на страницу входа и вернуться — отчёт и файл для автоисправления никуда не денутся.
const lastResult = new Map();

export default function CheckPage({ profileKey }) {
  const { profiles, error: profilesError, config } = useProfiles();
  const profile = profiles?.[profileKey];
  const [state, setStateRaw] = useState(() => lastResult.get(profileKey) || IDLE);

  const setState = (next) => setStateRaw((prev) => {
    const value = typeof next === "function" ? next(prev) : next;
    if (value.phase === "done") lastResult.set(profileKey, value);
    else if (value.phase === "idle") lastResult.delete(profileKey);
    return value;
  });

  // при переключении ВКР ↔ курсовая показываем результат именно этого типа работы
  useEffect(() => setStateRaw(lastResult.get(profileKey) || IDLE), [profileKey]);
  useEffect(() => {
    document.title = `${profile?.title ?? "Проверка"} — Нормоконтроль`;
  }, [profile]);

  async function onSubmit(file) {
    setState({ phase: "loading", report: null, error: null, file, upload: 0 });
    try {
      const report = await checkFile(file, profileKey, (upload) => setState((s) => ({ ...s, upload })));
      setState({ phase: "done", report, error: null, file, upload: null });
      window.scrollTo({ top: 0 });
    } catch (e) {
      setState({ ...IDLE, error: e.message });
    }
  }

  if (profilesError)
    return (
      <section className="container page">
        <div className="banner banner-error body-medium" role="alert"><Icon name="error" /> {profilesError}</div>
      </section>
    );
  if (!profile)
    return (
      <section className="container page loading"><md-circular-progress indeterminate="" /></section>
    );

  if (state.phase === "done")
    return (
      <section className="container page">
        <ReportView key={state.report.report_id} report={state.report}>
          {!state.report.clean && (
            <AutoFix file={state.file} uploadId={state.report.upload_id} profileKey={profileKey} />
          )}
        </ReportView>
        <div className="reset">
          <md-text-button onClick={() => setState(IDLE)}>
            <Icon name="back" slot="icon" />
            Проверить другой файл
          </md-text-button>
        </div>
      </section>
    );

  return (
    <section className="container page">
      <header className="hero">
        <span className="hero-art" aria-hidden="true"><Icon name={profileKey} size={176} /></span>
        <span className="hero-badge label-large"><Icon name="ok" size={18} /> Проверка по {profile.standard}</span>
        <h1 className="display-small hero-heading">{profile.title}</h1>
        <p className="body-large hero-tagline">{profile.tagline}</p>
        <ul className="highlights" aria-label="Ключевые нормы">
          {profile.highlights.map((h) => (
            <li key={h.icon} className="highlight label-large">
              <Icon name={h.icon} size={18} />
              {h.label}
            </li>
          ))}
        </ul>
      </header>
      <div className="banner banner-info body-medium">
        <Icon name="hint" />
        <span>
          <b>Загружайте только текст самой работы</b> — от «Введения» до приложений.
          Титульный лист, задание, отзыв и рецензию лучше убрать: они оформляются по другим правилам.
        </span>
      </div>

      {state.phase === "loading" ? (
        <Progress
          upload={state.upload}
          workingText="Проверяем оформление…"
          hint="Обычно несколько секунд, большие работы — до минуты."
        />
      ) : (
        <UploadForm onSubmit={onSubmit} serverError={state.error} />
      )}

      <NormsList norms={profile.norms} />
    </section>
  );
}
