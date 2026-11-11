type ValidationItem = { loc?: (string | number)[], msg?: string }

/** 接口报错时给人看的文字：FastAPI 的 {detail}（字符串或校验错误列表），或者普通的 Error */
export function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const { detail } = error as { detail: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return (detail as ValidationItem[])
        .map(({ loc = [], msg = '' }) => {
          const path = loc.filter(part => part !== 'body').join('.')
          return path ? `${path}：${msg}` : msg
        })
        .join('\n')
    }
  }
  if (error instanceof Error) return error.message
  return typeof error === 'string' ? error : '出错了'
}
