export const ALLOWED_EXTENSIONS = ['.docx', '.pdf'] as const
export const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

const extensionOf = (filename: string): string => {
  const dot = filename.lastIndexOf('.')
  return dot === -1 ? '' : filename.slice(dot).toLowerCase()
}

export const hasAllowedExtension = (filename: string): boolean =>
  ALLOWED_EXTENSIONS.includes(extensionOf(filename) as (typeof ALLOWED_EXTENSIONS)[number])

export const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} Б`
  const units = ['КБ', 'МБ', 'ГБ']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`
}

/** Returns a human-readable error, or null when the file passes client-side checks. */
export const validateFile = (file: File): string | null => {
  if (!hasAllowedExtension(file.name)) {
    return 'Поддерживаются только файлы .docx и .pdf.'
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `Файл слишком большой (${formatBytes(file.size)}). Максимум — ${formatBytes(MAX_FILE_SIZE_BYTES)}.`
  }
  if (file.size === 0) {
    return 'Файл пустой.'
  }
  return null
}
