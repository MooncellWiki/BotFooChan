import { client } from '~/client/client.gen'

export default defineNuxtPlugin((nuxtApp) => {
  // 后端要求写接口带这个头来挡 CSRF（见 src/plugins/webui/auth.py），干脆每个请求都带上
  client.setConfig({ headers: { 'X-WebUI': '1' } })

  client.interceptors.response.use((response, request) => {
    // 登录过期了就回登录页；/me 由路由中间件自己处理
    if (response.status === 401 && !new URL(request.url).pathname.endsWith('/me')) {
      useMe().value = null
      nuxtApp.runWithContext(() =>
        navigateTo({ path: '/login', query: { next: useRoute().fullPath } }),
      )
    }
    return response
  })
})
