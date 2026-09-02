import type { ApiErrorPayload, CheckReport } from './types.ts'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export class AbortedError extends Error {
  constructor() {
    super('Проверка отменена.')
    this.name = 'AbortedError'
  }
}

export type CheckPhase = 'uploading' | 'processing'

export interface CheckProgress {
  readonly phase: CheckPhase
  /** 0..100, only meaningful while phase === 'uploading' */
  readonly percent: number
}

export interface CheckHandle {
  readonly result: Promise<CheckReport>
  readonly abort: () => void
}

const isReportShape = (value: unknown): value is CheckReport => {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.filename === 'string' &&
    typeof v.isClean === 'boolean' &&
    typeof v.totalIssues === 'number' &&
    Array.isArray(v.notes) &&
    Array.isArray(v.categories)
  )
}

const parseErrorMessage = (responseText: string, fallback: string): string => {
  try {
    const payload = JSON.parse(responseText) as Partial<ApiErrorPayload>
    if (typeof payload.error === 'string' && payload.error.trim()) {
      return payload.error
    }
  } catch {
    // not JSON — fall through to the generic message
  }
  return fallback
}

/**
 * Uploads a document to /api/check using XHR (not fetch) specifically to get
 * upload progress events, which matters for large .docx/.pdf files on slow
 * connections.
 */
export function checkDocument(file: File, onProgress?: (progress: CheckProgress) => void): CheckHandle {
  const xhr = new XMLHttpRequest()
  const formData = new FormData()
  formData.append('file', file)

  const result = new Promise<CheckReport>((resolve, reject) => {
    xhr.upload.addEventListener('progress', (event) => {
      if (!event.lengthComputable) return
      onProgress?.({ phase: 'uploading', percent: Math.round((event.loaded / event.total) * 100) })
    })
    xhr.upload.addEventListener('load', () => {
      onProgress?.({ phase: 'processing', percent: 100 })
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        let parsed: unknown
        try {
          parsed = JSON.parse(xhr.responseText)
        } catch {
          reject(new ApiError('Сервер вернул неожиданный ответ. Попробуйте ещё раз.', xhr.status))
          return
        }
        if (!isReportShape(parsed)) {
          reject(new ApiError('Сервер вернул неожиданный ответ. Попробуйте ещё раз.', xhr.status))
          return
        }
        resolve(parsed)
        return
      }
      reject(new ApiError(parseErrorMessage(xhr.responseText, 'Не удалось проверить документ. Попробуйте ещё раз.'), xhr.status))
    })

    xhr.addEventListener('error', () => {
      reject(new ApiError('Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.', 0))
    })

    xhr.addEventListener('timeout', () => {
      reject(new ApiError('Сервер не ответил вовремя. Попробуйте ещё раз.', 0))
    })

    xhr.addEventListener('abort', () => {
      reject(new AbortedError())
    })
  })

  xhr.open('POST', '/api/check')
  xhr.timeout = 120_000
  xhr.send(formData)

  return { result, abort: () => xhr.abort() }
}
