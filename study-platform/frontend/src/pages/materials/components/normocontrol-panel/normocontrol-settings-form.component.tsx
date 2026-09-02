import { useEffect, useState, type FormEvent } from 'react';
import { Check, LoaderCircle, Settings2 } from 'lucide-react';
import { Button } from '@/components/button';
import { cn } from '@/lib/cn';
import { describeWsError } from '../../materials.utils';
import { useNormocontrolSettingsMutation } from '../../use-normocontrol';
import styles from './normocontrol-panel.style.module.css';
import type { NormocontrolSettings } from '../../use-normocontrol';

/** Настройки материала. Их немного: материал ничего не решает и не оценивает. */
export function NormocontrolSettingsForm({
  pageId,
  settings,
}: {
  pageId: string;
  settings: NormocontrolSettings;
}) {
  const [open, setOpen] = useState(false);
  const [instructions, setInstructions] = useState(settings.instructions ?? '');
  const [accepting, setAccepting] = useState(settings.accepting);
  const [problem, setProblem] = useState<string | null>(null);

  const save = useNormocontrolSettingsMutation(pageId);

  // Настройки могли измениться из другой вкладки, пока форма была закрыта.
  useEffect(() => {
    if (open) return;
    setInstructions(settings.instructions ?? '');
    setAccepting(settings.accepting);
  }, [open, settings.instructions, settings.accepting]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    try {
      await save.mutateAsync({ instructions: instructions.trim() || null, accepting });
      setOpen(false);
    } catch (error) {
      setProblem(describeWsError(error));
    }
  }

  if (!open) {
    return (
      <button type="button" className={styles.settingsToggle} onClick={() => setOpen(true)}>
        <Settings2 size={13} />
        {settings.configured ? 'Настройки материала' : 'Настроить материал'}
      </button>
    );
  }

  return (
    <form className={styles.settings} onSubmit={(event) => void handleSubmit(event)}>
      <div className={styles.field}>
        <label className={styles.label} htmlFor={`nc-instructions-${pageId}`}>
          Что написать студенту
        </label>
        <textarea
          id={`nc-instructions-${pageId}`}
          className={styles.textarea}
          value={instructions}
          rows={3}
          maxLength={8000}
          placeholder="Например: проверьте работу до сдачи на кафедру"
          onChange={(event) => setInstructions(event.target.value)}
        />
      </div>

      <label className={cn(styles.checkRow, !accepting && styles.checkRowOff)}>
        <input
          type="checkbox"
          checked={accepting}
          onChange={(event) => setAccepting(event.target.checked)}
        />
        <span>
          Принимать документы
          <small>
            Снимите, чтобы временно закрыть приём — например, пока сервис проверки недоступен.
            Готовые отчёты останутся на месте.
          </small>
        </span>
      </label>

      {problem && <p className={styles.error}>{problem}</p>}

      <div className={styles.settingsActions}>
        <Button type="submit" size="sm" disabled={save.isPending}>
          {save.isPending ? (
            <LoaderCircle size={14} className={styles.spin} />
          ) : (
            <Check size={14} />
          )}
          {save.isPending ? 'Сохраняем…' : 'Сохранить'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={save.isPending}
          onClick={() => setOpen(false)}
        >
          Отмена
        </Button>
      </div>
    </form>
  );
}
