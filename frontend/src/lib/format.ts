const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export const formatTimestamp = (iso: string): string => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return dateFormatter.format(date)
}

export const pluralizeIssues = (count: number): string => {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'замечание'
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return 'замечания'
  return 'замечаний'
}
