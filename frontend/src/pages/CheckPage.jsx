import { useEffect, useState } from "react";
import { useProfiles } from "../ProfilesContext.jsx";
import { checkFile } from "../api.js";
import UploadForm from "../components/UploadForm.jsx";
import NormsList from "../components/NormsList.jsx";
import ReportView from "../components/ReportView.jsx";
import AutoFix from "../components/AutoFix.jsx";
import { Icon } from "../ui.jsx";

const IDLE = { phase: "idle", report: null, error: null, file: null };

export default function CheckPage({ profileKey }) {
  const { profiles, error: profilesError, config } = useProfiles();
  const profile = profiles?.[profileKey];
  const [state, setState] = useState(IDLE);

  // при переключении ВКР ↔ курсовая сбрасываем результат
  useEffect(() => setState(IDLE), [profileKey]);
  useEffect(() => {
    document.title = `${profile?.title ?? "Проверка"} — Нормоконтроль`;
  }, [profile]);

  async function onSubmit(file) {
    setState({ phase: "loading", report: null, error: null, file });
    try {
      const report = await checkFile(file, profileKey);
      setState({ phase: "done", report, error: null, file });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setState({ phase: "idle", report: null, error: e.message, file: null });
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
          {config.autofix_enabled && !state.report.clean && (
            <AutoFix file={state.file} profileKey={profileKey} />
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
      <p className="label-large eyebrow">{profile.standard}</p>
      <h1 className="display-small hero-title">{profile.title}</h1>
      <p className="body-large supporting">{profile.description}</p>
      <div className="banner banner-info body-medium">
        <Icon name="hint" />
        <span>
          <b>Загружайте только текст самой работы</b> — от «Введения» до приложений.
          Титульный лист, задание, отзыв и рецензию лучше убрать: они оформляются по другим правилам.
        </span>
      </div>

      {state.phase === "loading" ? (
        <div className="loading">
          <md-circular-progress indeterminate="" />
          <p className="body-large">Разбираем документ…</p>
          <p className="body-medium">Обычно это занимает несколько секунд, большие работы — до минуты.</p>
        </div>
      ) : (
        <UploadForm onSubmit={onSubmit} serverError={state.error} />
      )}

      <NormsList norms={profile.norms} />
    </section>
  );
}
