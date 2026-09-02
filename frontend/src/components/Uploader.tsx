import { useId, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react'
import type { CheckStatus } from '../hooks/useDocumentCheck.ts'
import { ALLOWED_EXTENSIONS, formatBytes } from '../lib/validation.ts'
import './Uploader.css'

interface UploaderProps {
  readonly file: File | null
  readonly status: CheckStatus
  readonly errorMessage: string | null
  readonly onSelectFile: (file: File | null) => void
  readonly onSubmit: () => void
}

const acceptAttr = ALLOWED_EXTENSIONS.join(',')

export function Uploader({ file, status, errorMessage, onSelectFile, onSubmit }: UploaderProps) {
  const inputId = useId()
  const errorId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const busy = status === 'uploading' || status === 'processing'

  const openPicker = () => inputRef.current?.click()

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openPicker()
    }
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSelectFile(event.target.files?.[0] ?? null)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (busy) return
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) onSelectFile(dropped)
  }

  return (
    <form
      className="nc-uploader"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
      noValidate
    >
      <div
        className={`nc-dropzone${isDragging ? ' nc-dropzone--drag' : ''}${busy ? ' nc-dropzone--busy' : ''}`}
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-disabled={busy}
        aria-describedby={file ? `${inputId}-filename` : undefined}
        onClick={busy ? undefined : openPicker}
        onKeyDown={busy ? undefined : handleKeyDown}
        onDragOver={(event) => {
          event.preventDefault()
          if (!busy) setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M12 3v12m0-12l-4 4m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
        </svg>
        <span className="nc-dropzone__main">Перетащите файл сюда или нажмите</span>
        <span className="nc-dropzone__hint">.docx или .pdf, до 20&nbsp;МБ</span>
      </div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={acceptAttr}
        hidden
        disabled={busy}
        onChange={handleInputChange}
        aria-label="Выберите файл для проверки"
      />

      {file && (
        <div id={`${inputId}-filename`} className="nc-filename">
          {file.name} <span className="nc-filename__size">· {formatBytes(file.size)}</span>
        </div>
      )}

      <button type="submit" className="nc-submit" disabled={!file || busy}>
        {busy ? 'Проверяем…' : 'Проверить документ'}
      </button>

      <div id={errorId} className="nc-form-error" role="alert" hidden={!errorMessage}>
        {errorMessage}
      </div>
    </form>
  )
}
