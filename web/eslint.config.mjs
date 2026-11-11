// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt({
  // 生成的接口客户端，不归我们管
  ignores: ['app/client/**'],
})
