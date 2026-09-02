import { useRef, useState, type FormEvent } from 'react';
import { FileCheck2, FileUp, LoaderCircle, Send, X } from 'lucide-react';
import { Button } from '@/components/button';
import { cn } from '@/lib/cn';
import { describeWsError } from '../../materials.utils';
import { useSubmitNormocontrol } from '../../use-normocontrol';
import { formatSize } from './normocontrol-panel.utils';
import styles from './normocontrol-panel.style.module.css';
import type { NormocontrolSettings } from '../../use-normocontrol';

export interface NormocontrolUploaderProps {
  pageId: string;
  settings: NormocontrolSettings;
  /** Сколько работ этого человека уже ждут очереди. */
  pending: number;
  disabled: boolean;
}

/**
 * Отправка документа на проверку.
 *
 * Один файл за раз: проверка идёт десятки секунд, и пачка из десяти работ —
 * это не то, чего человек хочет, а то, чем он случайно займёт очередь.
 */
export function NormocontrolUploader({
  pageId,
  settings,
  pending,
  disabled,
}: NormocontrolUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = useSubmitNormocontrol(pageId);
  const accept = settings.allowed_extensions.join(',');

  function pick(picked: FileList | null) {
    const chosen = picked?.[0] ?? null;
    if (!chosen) return;
    setProblem(null);

    const extension = chosen.name.slice(chosen.name.lastIndexOf('.')).toLowerCase();
    if (!settings.allowed_extensions.includes(extension)) {
      setProblem(`Проверяются только ${settings.allowed_extensions.join(' и ')}.`);
      return;
    }
    // Проверка размера здесь — вежливость, а не защита: сервер её повторяет.
    // Но отправить впустую сто мегабайт и узнать об этом после — обидно.
    if (chosen.size > settings.max_file_size) {
      setProblem(`Файл больше ${formatSize(settings.max_file_size)}.`);
      return;
    }
    setFile(chosen);
    if (inputRef.current) inputRef.current.value = '';
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setProblem('Выберите документ.');
      return;
    }
    setProblem(null);
    try {
      await submit.mutateAsync(file);
      setFile(null);
    } catch (error) {
      setProblem(describeWsError(error));
    }
  }

  return (
    <form
      className={styles.uploader}
      aria-busy={submit.isPending}
      onSubmit={(event) => void handleSubmit(event)}
    >
      <label
        className={cn(
          styles.dropzone,
          file && styles.dropzoneReady,
          submit.isPending && styles.dropzoneSending,
        )}
      >
        {submit.isPending ? (
          <LoaderCircle size={18} className={styles.spin} />
        ) : file ? (
          <FileCheck2 size={18} className={styles.dropzoneIcon} />
        ) : (
          <FileUp size={18} className={styles.dropzoneIcon} />
        )}
        <span>
          <strong>{file ? file.name : 'Выберите документ'}</strong>
          <small>
            {file
              ? formatSize(file.size)
              : `${settings.allowed_extensions.join(', ')} — до ${formatSize(
                  settings.max_file_size,
                )}`}
          </small>
        </span>
        <input
          ref={inputRef}
          type="file"
          className={styles.fileInput}
          accept={accept}
          disabled={disabled || submit.isPending}
          onChange={(event) => pick(event.target.files)}
        />
      </label>

      {submit.isPending && (
        <div className={styles.uploadProgress} role="progressbar" aria-label="Документ загружается">
          <span />
        </div>
      )}

      {file && (
        <button
          type="button"
          className={styles.clearFile}
          aria-label="Убрать выбранный документ"
          onClick={() => setFile(null)}
        >
          <X size={13} /> Убрать
        </button>
      )}

      {problem && <p className={styles.error}>{problem}</p>}

      <div className={styles.uploaderActions}>
        <Button type="submit" size="sm" disabled={disabled || submit.isPending || !file}>
          {submit.isPending ? (
            <LoaderCircle size={14} className={styles.spin} />
          ) : (
            <Send size={14} />
          )}
          {submit.isPending ? 'Отправляем…' : 'Проверить'}
        </Button>
        {pending > 0 && (
          <span className={styles.pendingHint}>
            <i aria-hidden="true" /> Уже в работе: {pending}. Результат придёт сам.
          </span>
        )}
      </div>
    </form>
  );
}
