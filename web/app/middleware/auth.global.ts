import { getMe } from '~/client'

// 除了登录页，进哪个页面都要先确认登录了
export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path === '/login') return
  const me = useMe()
  if (me.value) return

  const { data, response } = await getMe()
  if (data) {
    me.value = data
    return
  }
  if (response?.status === 401) {
    return navigateTo({ path: '/login', query: { next: to.fullPath } })
  }
  // 其它错误（后端没起来之类）放行，让页面自己把错误显示出来
})
