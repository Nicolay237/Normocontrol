import { useCallback, useRef, useState } from 'react'
import { AbortedError, ApiError, checkDocument, type CheckHandle } from '../api/client.ts'
import type { CheckReport } from '../api/types.ts'
import { validateFile } from '../lib/validation.ts'

export type CheckStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error'

export interface DocumentCheckState {
  readonly status: CheckStatus
  readonly file: File | null
  readonly progress: number
  readonly report: CheckReport | null
  readonly errorMessage: string | null
}

export interface DocumentCheckControls extends DocumentCheckState {
  readonly selectFile: (file: File | null) => void
  readonly submit: () => void
  readonly cancel: () => void
  readonly reset: () => void
}

const initialState: DocumentCheckState = {
  status: 'idle',
  file: null,
  progress: 0,
  report: null,
  errorMessage: null,
}

export function useDocumentCheck(): DocumentCheckControls {
  const [state, setState] = useState<DocumentCheckState>(initialState)
  const handleRef = useRef<CheckHandle | null>(null)

  const selectFile = useCallback((file: File | null) => {
    if (!file) {
      setState((prev) => ({ ...prev, file: null, errorMessage: null }))
      return
    }
    const validationError = validateFile(file)
    setState({
      status: 'idle',
      file: validationError ? null : file,
      progress: 0,
      report: null,
      errorMessage: validationError,
    })
  }, [])

  const submit = useCallback(() => {
    setState((prev) => {
      if (!prev.file || prev.status === 'uploading' || prev.status === 'processing') return prev

      const handle = checkDocument(prev.file, (p) => {
        setState((current) => ({ ...current, status: p.phase, progress: p.percent }))
      })
      handleRef.current = handle

      handle.result
        .then((report) => {
          setState((current) => ({ ...current, status: 'success', report, errorMessage: null }))
        })
        .catch((error: unknown) => {
          if (error instanceof AbortedError) {
            setState((current) => ({ ...current, status: 'idle', progress: 0 }))
            return
          }
          const message = error instanceof ApiError ? error.message : 'Произошла непредвиденная ошибка. Попробуйте ещё раз.'
          setState((current) => ({ ...current, status: 'error', errorMessage: message, progress: 0 }))
        })
        .finally(() => {
          handleRef.current = null
        })

      return { ...prev, status: 'uploading', progress: 0, errorMessage: null }
    })
  }, [])

  const cancel = useCallback(() => {
    handleRef.current?.abort()
  }, [])

  const reset = useCallback(() => {
    handleRef.current?.abort()
    setState(initialState)
  }, [])

  return { ...state, selectFile, submit, cancel, reset }
}
