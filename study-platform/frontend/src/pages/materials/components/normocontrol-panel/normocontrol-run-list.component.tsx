import { useEffect, useState } from 'react';
import {
  ChevronDown,
  Clock3,
  FileText,
  LoaderCircle,
  TriangleAlert,
  UsersRound,
  X,
} from 'lucide-react';
import { Avatar } from '@/components/avatar';
import { Button } from '@/components/button';
import { cn } from '@/lib/cn';
import { plural } from '@/lib/plural';
import { describeWsError } from '../../materials.utils';
import { useCancelNormocontrolRun } from '../../use-normocontrol';
import { NormocontrolReportView } from './normocontrol-report.component';
import {
  describeFailure,
  formatMoment,
  formatSize,
  statusTone,
  STATUS_LABEL,
} from './normocontrol-panel.utils';
import styles from './normocontrol-panel.style.module.css';
import type { NormocontrolRun } from '../../use-normocontrol';

/** История проверок. Самая свежая раскрыта — за ней и приходят. */
export function NormocontrolRunList({
  pageId,
  runs,
  showAuthors,
}: {
  pageId: string;
  runs: readonly NormocontrolRun[];
  showAuthors: boolean;
}) {
  const newestId = runs[0]?.id;
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(newestId ? [newestId] : []));
  const [problem, setProblem] = useState<string | null>(null);
  const cancel = useCancelNormocontrolRun(pageId);

  useEffect(() => {
    if (!newestId) return;
    setExpanded((current) => (current.has(newestId) ? current : new Set<string>([newestId])));
  }, [newestId]);

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCancel(runId: string) {
    setProblem(null);
    try {
      await cancel.mutateAsync(runId);
    } catch (error) {
      setProblem(describeWsError(error));
    }
  }

  return (
    <>
      {problem && <p className={styles.error}>{problem}</p>}
      {showAuthors && (
        <div className={styles.reviewHeading}>
          <UsersRound size={14} />
          <span>Проверки пользователей</span>
        </div>
      )}
      {runs.length === 0 && (
        <p className={styles.empty}>
          {showAuthors
            ? 'Пользователи ещё не отправляли документы на проверку.'
            : 'Здесь появятся ваши проверки. Отчёт видите только вы и преподаватель.'}
        </p>
      )}
      <ol className={styles.runs} aria-label="История проверок">
        {runs.map((run) => {
          const isOpen = expanded.has(run.id);
          const tone = statusTone(run);
          const waiting = run.status === 'queued' || run.status === 'running';
          const moment = formatMoment(run.finished_at ?? run.created_at);
          return (
            <li
              key={`${run.id}:${run.status}`}
              className={cn(styles.run, waiting && styles.runWaiting)}
            >
              <div className={styles.runHead}>
                {/* Значок и имя — одно целое: по отдельности на узкой панели
                    значок уезжал на свою строку. */}
                <div className={styles.runIdentity}>
                  <FileText size={14} className={styles.runIcon} />
                  <div className={styles.runTitle}>
                    <span className={styles.runName}>{run.original_name ?? 'Документ'}</span>
                    {/* Каждый факт — отдельная неразрывная единица: одной
                      строкой они рвались посередине, оставляя часы на одной
                      строке, а размер на другой. */}
                    <span className={styles.runMeta}>
                      {showAuthors && run.author && (
                        <span className={styles.runAuthor}>
                          <Avatar
                            id={run.author.id}
                            name={run.author.display_name}
                            avatarId={run.author.avatar_id}
                            size="xs"
                          />
                          <strong>{run.author.display_name}</strong>
                          <small>@{run.author.username}</small>
                        </span>
                      )}
                      {moment && (
                        <span>
                          <Clock3 size={10} /> {moment}
                        </span>
                      )}
                      {run.size ? <span>{formatSize(run.size)}</span> : null}
                    </span>
                  </div>
                </div>

                <span className={cn(styles.chip, styles[`chip_${tone}`])}>
                  {run.status === 'running' && <LoaderCircle size={11} className={styles.spin} />}
                  {run.status === 'queued' && <i className={styles.queueDot} aria-hidden="true" />}
                  {run.status === 'done' && run.report
                    ? run.report.is_clean
                      ? 'Без замечаний'
                      : `${run.report.total_issues} ${plural(run.report.total_issues, [
                          'замечание',
                          'замечания',
                          'замечаний',
                        ])}`
                    : (STATUS_LABEL[run.status] ?? run.status)}
                </span>

                {run.status === 'queued' && run.queue_position !== null && (
                  <span className={styles.queuePosition}>{run.queue_position}-й в очереди</span>
                )}

                {run.status === 'queued' && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={cancel.isPending}
                    onClick={() => void handleCancel(run.id)}
                  >
                    <X size={13} /> Отменить
                  </Button>
                )}

                {(run.report || run.error_code) && (
                  <button
                    type="button"
                    className={styles.runToggle}
                    aria-label={isOpen ? 'Свернуть проверку' : 'Раскрыть проверку'}
                    aria-expanded={isOpen}
                    onClick={() => toggle(run.id)}
                  >
                    <ChevronDown size={14} className={cn(isOpen && styles.runToggleOpen)} />
                  </button>
                )}
              </div>

              {isOpen && run.error_code && (
                <div className={styles.failure}>
                  <TriangleAlert size={14} />
                  <span>{describeFailure(run.error_code)}</span>
                </div>
              )}

              {isOpen && run.report && (
                <div className={styles.runBody}>
                  <NormocontrolReportView report={run.report} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </>
  );
}
