import { pluralizeIssues } from '../lib/format.ts'

interface ReportStampProps {
  readonly isClean: boolean
  readonly totalIssues: number
}

export function ReportStamp({ isClean, totalIssues }: ReportStampProps) {
  const label = isClean ? 'СООТВЕТСТВУЕТ НОРМАМ' : `${totalIssues} ${pluralizeIssues(totalIssues).toUpperCase()}`

  return (
    <div className={`nc-report-stamp ${isClean ? 'nc-report-stamp--ok' : 'nc-report-stamp--bad'}`}>
      {label}
    </div>
  )
}
