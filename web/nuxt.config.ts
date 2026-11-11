// 管理后台前端：只生成静态文件（SPA），由 bot 进程在 /admin/ 下托管，见 src/plugins/webui
export default defineNuxtConfig({
  modules: ['@nuxt/eslint', '@nuxt/ui', '@pinia/nuxt', '@pinia/colada-nuxt'],
  ssr: false,
  devtools: { enabled: true },
  app: {
    baseURL: '/admin/',
    head: {
      title: 'BotFooChan',
      htmlAttrs: { lang: 'zh-CN' },
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/admin/favicon.svg' }],
    },
  },
  css: ['~/assets/css/main.css'],
  ui: {
    // 界面是中文，用系统字体就好，构建时也不用去拉 Google Fonts
    fonts: false,
  },
  compatibilityDate: '2026-11-01',
  nitro: {
    // pnpm dev 时把接口转给本地跑着的 bot，端口不是 8086 时用 WEBUI_DEV_API 指过去。
    // 保留原来的 Host 头：后端按它拼 OAuth 回调地址，登录完才会回到 dev server
    devProxy: {
      '/admin/api': {
        target: `${process.env.WEBUI_DEV_API ?? 'http://127.0.0.1:8086'}/admin/api`,
      },
    },
  },
  icon: {
    // 用到的图标打进包里，不在运行时去请求 Iconify 的接口
    provider: 'none',
    clientBundle: { scan: true },
  },
})
