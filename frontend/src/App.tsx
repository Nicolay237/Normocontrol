import { FeatureGrid } from './components/FeatureGrid.tsx'
import { Footer } from './components/Footer.tsx'
import { Hero } from './components/Hero.tsx'
import { LoadingState } from './components/LoadingState.tsx'
import { NavBar } from './components/NavBar.tsx'
import { ReportView } from './components/ReportView.tsx'
import { useDocumentCheck } from './hooks/useDocumentCheck.ts'
import { pluralizeIssues } from './lib/format.ts'

const STATUS_ANNOUNCEMENT: Record<string, string> = {
  processing: 'Разбираем документ…',
  success: 'Проверка завершена.',
  error: 'Не удалось проверить документ.',
}

function App() {
  const { status, file, progress, report, errorMessage, selectFile, submit, cancel, reset } = useDocumentCheck()
  const isBusy = status === 'uploading' || status === 'processing'
  const showLanding = !isBusy && status !== 'success'

  return (
    <>
      <NavBar />

      <div className="visually-hidden" role="status" aria-live="polite">
        {status === 'success' && report
          ? `Проверка завершена: ${report.isClean ? 'замечаний не найдено' : `${report.totalIssues} ${pluralizeIssues(report.totalIssues)}`}.`
          : STATUS_ANNOUNCEMENT[status]}
      </div>

      {showLanding && (
        <>
          <Hero file={file} status={status} errorMessage={errorMessage} onSelectFile={selectFile} onSubmit={submit} />
          <FeatureGrid />
        </>
      )}

      {isBusy && <LoadingState status={status} progress={progress} fileName={file?.name ?? null} onCancel={cancel} />}

      {status === 'success' && report && <ReportView report={report} onReset={reset} />}

      <Footer />
    </>
  )
}

export default App
