import { CategoryAccordion } from './CategoryAccordion.tsx'
import { ReportStamp } from './ReportStamp.tsx'
import type { CheckReport } from '../api/types.ts'
import { formatTimestamp } from '../lib/format.ts'
import './ReportView.css'

interface ReportViewProps {
  readonly report: CheckReport
  readonly onReset: () => void
}

export function ReportView({ report, onReset }: ReportViewProps) {
  return (
    <section className="nc-results" aria-label="Результат проверки">
      <div className="nc-report-card">
        <header className="nc-report-card__header">
          <div>
            <h1>Отчёт нормоконтроля</h1>
            <div className="nc-report-card__meta">
              {report.filename} · {formatTimestamp(report.generatedAt)}
            </div>
          </div>
          <ReportStamp isClean={report.isClean} totalIssues={report.totalIssues} />
        </header>

        <hr />

        {report.notes.length > 0 && (
          <ul className="nc-report-card__notes">
            {report.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        )}

        {report.isClean ? (
          <p className="nc-report-card__clean">Замечаний не обнаружено. Документ соответствует заданным нормам.</p>
        ) : (
          report.categories.map((category) => <CategoryAccordion key={category.name} category={category} />)
        )}

        <footer className="nc-report-card__footer">
          Нормы: ГОСТ 7.32-2017 (типовые требования для ВКР) · сгенерировано автоматически, не заменяет решение
          нормоконтролёра
        </footer>
      </div>

      <div className="nc-results__actions">
        <button type="button" className="nc-print-btn" onClick={() => window.print()}>
          Сохранить / распечатать отчёт
        </button>
        <button type="button" className="nc-reset-btn" onClick={onReset}>
          ← Проверить другой файл
        </button>
      </div>
    </section>
  )
}
