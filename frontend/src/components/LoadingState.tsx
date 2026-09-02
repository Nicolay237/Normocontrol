import type { CheckStatus } from '../hooks/useDocumentCheck.ts'
import './LoadingState.css'

interface LoadingStateProps {
  readonly status: CheckStatus
  readonly progress: number
  readonly fileName: string | null
  readonly onCancel: () => void
}

export function LoadingState({ status, progress, fileName, onCancel }: LoadingStateProps) {
  const isUploading = status === 'uploading'

  return (
    <div className="nc-loading" role="status" aria-live="polite">
      {isUploading ? (
        <div className="nc-loading__bar-track" aria-hidden="true">
          <div className="nc-loading__bar-fill" style={{ width: `${progress}%` }} />
        </div>
      ) : (
        <div className="nc-spinner" aria-hidden="true" />
      )}
      <p className="nc-loading__label">
        {isUploading ? `Загружаем «${fileName}»… ${progress}%` : 'Разбираем документ…'}
      </p>
      <button type="button" className="nc-loading__cancel" onClick={onCancel}>
        Отменить
      </button>
    </div>
  )
}
