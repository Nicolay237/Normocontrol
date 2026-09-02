import type { NormocontrolRun } from '../../use-normocontrol';

export const STATUS_LABEL: Record<string, string> = {
  draft: 'Черновик',
  queued: 'В очереди',
  running: 'Проверяется',
  done: 'Проверено',
  failed: 'Не удалось',
  cancelled: 'Отменено',
};

export type StatusTone = 'wait' | 'done' | 'issues' | 'bad' | 'idle';

export function statusTone(run: NormocontrolRun): StatusTone {
  if (run.status === 'queued' || run.status === 'running') return 'wait';
  if (run.status === 'failed') return 'bad';
  if (run.status === 'cancelled') return 'idle';
  if (run.status !== 'done') return 'idle';
  // Проверено — но «чисто» и «есть замечания» это разные новости.
  return run.report && run.report.is_clean ? 'done' : 'issues';
}

/**
 * Почему проверка не состоялась — словами.
 *
 * Коды приходят от бэкенда и не зависят от версии внешнего сервиса: его
 * собственный текст меняется вместе с ним, и показывать его нельзя.
 */
export const FAILURE_LABEL: Record<string, string> = {
  document_rejected: 'Документ не удалось разобрать. Возможно, он повреждён или защищён паролем.',
  unsupported_format: 'Такой формат не проверяется. Нужен .docx или .pdf.',
  file_too_large: 'Документ слишком большой для проверки.',
  file_missing: 'Документ не найден — вероятно, он уже удалён.',
  timeout: 'Проверка заняла слишком долго. Попробуйте ещё раз.',
  service_unavailable: 'Сервис проверки сейчас недоступен. Попробуйте позже.',
  incompatible_report: 'Сервис проверки ответил в незнакомом формате. Мы уже знаем об этом.',
  processing_error:
    'Во время проверки произошёл внутренний сбой. Попробуйте отправить документ ещё раз.',
};

export function describeFailure(code: string | null | undefined): string {
  if (!code) return 'Проверка не удалась.';
  return FAILURE_LABEL[code] ?? 'Проверка не удалась.';
}

export function formatSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

export function formatMoment(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return date.toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
