import { useEffect, useState } from "react";

const UPLOAD_SHARE = 0.4; // доля шкалы под отправку файла, остальное — обработка на сервере
const CAP = 0.95;         // до ответа сервера шкала не доходит до конца

/**
 * Ход запроса одной шкалой, которая движется только вперёд:
 *  - пока файл уходит на сервер — реальный процент отправки;
 *  - пока сервер работает — плавное продвижение к 95 % (сколько точно осталось,
 *    сервер не сообщает, поэтому шкала замедляется, но никогда не откатывается).
 *
 * Своя шкала вместо md-linear-progress: «неопределённая» анимация Material
 * на телефонах выглядела как полоска, которая доходит до трети и откатывается.
 */
export default function Progress({ upload, uploadingText = "Отправляем файл", workingText, hint, expectedSec = 6 }) {
  const hasUpload = upload !== null && upload !== undefined;
  const uploading = hasUpload && upload < 1;
  const [work, setWork] = useState(0);

  useEffect(() => {
    if (uploading) return undefined;
    const t0 = performance.now();
    const id = setInterval(() => {
      const t = (performance.now() - t0) / 1000;
      setWork(1 - Math.exp(-t / expectedSec)); // ~63 % пути за expectedSec, дальше всё медленнее
    }, 100);
    return () => clearInterval(id);
  }, [uploading, expectedSec]);

  const start = hasUpload ? UPLOAD_SHARE : 0;
  const value = uploading ? upload * UPLOAD_SHARE : start + (CAP - start) * work;

  return (
    <div className="progress-block" role="status" aria-live="polite">
      <div
        className="bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value * 100)}
      >
        <div className="bar-fill" style={{ transform: `scaleX(${value})` }} />
      </div>
      <p className="body-large progress-title">
        {uploading ? `${uploadingText}…` : workingText}
      </p>
      {hint && !uploading && <p className="body-medium progress-hint">{hint}</p>}
    </div>
  );
}
