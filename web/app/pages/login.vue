<script setup lang="ts">
definePageMeta({ layout: false })

const route = useRoute()
const config = useRuntimeConfig()

const ERRORS: Record<string, string> = {
  denied: '你取消了 GitHub 授权',
  expired: '登录超时了，再试一次',
  github: 'GitHub 那边出错了，稍后再试',
  unavailable: '后台没有配置 GitHub OAuth，现在登录不了',
}

const error = computed(() => {
  const code = route.query.error
  if (typeof code !== 'string') return null
  if (code === 'forbidden') {
    const login = typeof route.query.login === 'string' ? route.query.login : ''
    return `GitHub 账号 ${login} 不在管理员名单里`
  }
  return ERRORS[code] ?? '登录失败'
})

// 登录是整页跳转：先到后端，后端再跳去 GitHub 授权，回来时种好 cookie 跳回 next
const loginHref = computed(() => {
  const base = config.app.baseURL.replace(/\/$/, '')
  const next = route.query.next
  const path = typeof next === 'string' && next.startsWith('/') && !next.startsWith('//')
    ? next
    : '/'
  return `${base}/api/auth/login?${new URLSearchParams({ next: base + path })}`
})
</script>

<template>
  <div class="flex min-h-svh items-center justify-center p-4">
    <UPageCard
      class="w-full max-w-sm"
      icon="i-lucide-bot"
      title="BotFooChan 管理后台"
      description="用 GitHub 账号登录，只有管理员名单里的账号能进来。"
    >
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="error"
      />
      <UButton
        :to="loginHref"
        external
        block
        size="lg"
        icon="i-lucide-github"
        label="用 GitHub 登录"
      />
    </UPageCard>
  </div>
</template>
