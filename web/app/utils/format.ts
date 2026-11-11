const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

export function formatBytes(bytes: number): string {
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${BYTE_UNITS[unit]}`
}

/** 时长，精确到分钟：「3 天 4 小时」「2 小时 5 分」「12 分钟」 */
export function formatDuration(milliseconds: number): string {
  const minutes = Math.max(0, Math.floor(milliseconds / 60_000))
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  if (days) return `${days} 天 ${hours} 小时`
  if (hours) return `${hours} 小时 ${minutes % 60} 分`
  return `${minutes} 分钟`
}

const dateTimeFormat = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'medium' })
const timeFormat = new Intl.DateTimeFormat('zh-CN', { timeStyle: 'medium' })

export function formatDateTime(value: string | number | Date): string {
  return dateTimeFormat.format(new Date(value))
}

export function formatTime(value: string | number | Date): string {
  return timeFormat.format(new Date(value))
}
