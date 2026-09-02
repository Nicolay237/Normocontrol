import { useState } from 'react';
import { ChevronDown, CircleCheck, Info } from 'lucide-react';
import { cn } from '@/lib/cn';
import { plural } from '@/lib/plural';
import styles from './normocontrol-panel.style.module.css';
import type { NormocontrolReport } from '../../use-normocontrol';

const INITIAL_ISSUES = 4;

/**
 * Отчёт внешнего сервиса.
 *
 * Категории рисуются обобщённо и ниоткуда не перечисляются: сервис
 * дорабатывается, проверок в нём становится больше, и новая категория должна
 * появляться здесь сама. Порядок — как прислали.
 */
export function NormocontrolReportView({ report }: { report: NormocontrolReport }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  function toggle(name: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  if (report.is_clean) {
    return (
      <div className={styles.clean}>
        <CircleCheck size={16} />
        <span>
          <strong>Замечаний нет</strong>
          <small>Оформление документа соответствует проверяемым требованиям.</small>
        </span>
      </div>
    );
  }

  return (
    <div className={styles.report}>
      {report.notes.length > 0 && (
        <div className={styles.notes}>
          <Info size={13} />
          <div>
            {report.notes.map((note) => (
              <p key={note}>{note}</p>
            ))}
          </div>
        </div>
      )}

      <ul className={styles.categories}>
        {report.categories.map((category) => {
          const isOpen = expanded.has(category.name);
          const visible = isOpen ? category.issues : category.issues.slice(0, INITIAL_ISSUES);
          const hidden = category.issues.length - visible.length;
          return (
            <li key={category.name} className={styles.category}>
              <div className={styles.categoryHead}>
                <span className={styles.categoryName}>{category.name}</span>
                <span className={styles.categoryCount}>
                  {category.issues.length}{' '}
                  {plural(category.issues.length, ['замечание', 'замечания', 'замечаний'])}
                </span>
              </div>
              <div className={styles.issueTableWrap}>
                <table className={styles.issueTable}>
                  <thead>
                    <tr>
                      <th scope="col">Где найдено</th>
                      <th scope="col">Что исправить</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((issue, index) => (
                      <tr key={`${issue.location}:${index}`}>
                        <td className={styles.issueLocation}>{issue.location}</td>
                        <td className={styles.issueMessage}>{issue.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(hidden > 0 || isOpen) && (
                  <button
                    type="button"
                    className={styles.moreIssues}
                    aria-expanded={isOpen}
                    onClick={() => toggle(category.name)}
                  >
                    <ChevronDown size={13} className={cn(isOpen && styles.moreIssuesOpen)} />
                    {isOpen ? 'Свернуть список' : `Показать ещё ${hidden}`}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
