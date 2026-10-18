/**
 * Ход запроса: пока файл отправляется — шкала с процентами, после — неопределённый
 * прогресс «обрабатываем». Без этого на медленном мобильном интернете кажется, что всё зависло.
 */
export default function Progress({ upload, uploadingText = "Отправляем файл", workingText, hint }) {
  const uploading = upload !== null && upload < 1;
  const pct = Math.round((upload ?? 0) * 100);
  return (
    <div className="progress-block" role="status" aria-live="polite">
      {uploading ? (
        <md-linear-progress value={String(upload)} class="progress" />
      ) : (
        <md-linear-progress indeterminate="" class="progress" />
      )}
      <p className="body-large progress-title">
        {uploading ? `${uploadingText}… ${pct}%` : workingText}
      </p>
      {hint && !uploading && <p className="body-medium progress-hint">{hint}</p>}
    </div>
  );
}
