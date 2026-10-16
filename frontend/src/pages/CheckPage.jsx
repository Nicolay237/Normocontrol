import { useEffect, useState } from "react";
import { useProfiles } from "../ProfilesContext.jsx";
import { checkFile } from "../api.js";
import UploadForm from "../components/UploadForm.jsx";
import NormsList from "../components/NormsList.jsx";
import ReportView from "../components/ReportView.jsx";

const IDLE = { phase: "idle", report: null, error: null };

export default function CheckPage({ profileKey }) {
  const { profiles, error: profilesError } = useProfiles();
  const profile = profiles?.[profileKey];
  const [state, setState] = useState(IDLE);

  // при переключении ВКР ↔ курсовая сбрасываем результат
  useEffect(() => setState(IDLE), [profileKey]);
  useEffect(() => {
    document.title = `${profile?.title ?? "Проверка"} — Нормоконтроль`;
  }, [profile]);

  async function onSubmit(file) {
    setState({ phase: "loading", report: null, error: null });
    try {
      const report = await checkFile(file, profileKey);
      setState({ phase: "done", report, error: null });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setState({ phase: "idle", report: null, error: e.message });
    }
  }

  if (profilesError) return <section className="page"><p className="form-error">{profilesError}</p></section>;
  if (!profile) return <section className="page"><p className="muted">Загрузка…</p></section>;

  if (state.phase === "done")
    return (
      <section className="page">
        <ReportView report={state.report} />
        <button className="reset-btn" onClick={() => setState(IDLE)}>
          ← Проверить другой файл
        </button>
      </section>
    );

  return (
    <section className="page">
      <p className="eyebrow">{profile.standard}</p>
      <h1>{profile.title}</h1>
      <p className="hero-sub">{profile.description}</p>
      <p className="hero-sub upload-note">
        <strong>Загружайте только текст самой работы</strong> — от «Введения» до приложений.
        Титульный лист, задание, отзыв и рецензию лучше убрать: они оформляются по другим правилам.
      </p>

      {state.phase === "loading" ? (
        <div className="loading">
          <div className="spinner" aria-hidden="true" />
          <p>Разбираем документ…</p>
        </div>
      ) : (
        <UploadForm onSubmit={onSubmit} serverError={state.error} />
      )}

      <NormsList norms={profile.norms} />
    </section>
  );
}
