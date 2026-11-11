<script setup lang="ts">
import type { DropdownMenuItem, NavigationMenuItem } from '@nuxt/ui'
import { logout } from '~/client'

const me = useMe()
const toast = useToast()

const nav: NavigationMenuItem[][] = [
  [
    { label: '概览', icon: 'i-lucide-gauge', to: '/' },
    { label: '日志', icon: 'i-lucide-scroll', to: '/logs' },
  ],
  [
    { label: 'LLM', type: 'label' },
    { label: '模型', icon: 'i-lucide-brain-circuit', to: '/llm/models' },
    { label: '模型路由', icon: 'i-lucide-route', to: '/llm/routes' },
    { label: '提示词', icon: 'i-lucide-message-square-text', to: '/llm/prompts' },
    { label: '调用记录', icon: 'i-lucide-history', to: '/llm/invocations' },
  ],
  [
    { label: '数据', type: 'label' },
    { label: '订阅推送', icon: 'i-lucide-rss', to: '/data/bison' },
    { label: 'GitHub', icon: 'i-lucide-github', to: '/data/github' },
    { label: '群号绑定', icon: 'i-lucide-link', to: '/data/bindings' },
    { label: 'FGO 维护推送', icon: 'i-lucide-bell-ring', to: '/data/fgo' },
    { label: '群友记忆', icon: 'i-lucide-notebook-text', to: '/data/memory' },
  ],
  [
    { label: '运维', type: 'label' },
    { label: '插件', icon: 'i-lucide-puzzle', to: '/ops/plugins' },
    { label: '定时任务', icon: 'i-lucide-calendar-clock', to: '/ops/scheduler' },
    { label: 'Torappu 重跑', icon: 'i-lucide-rotate-cw', to: '/ops/torappu' },
  ],
  [
    { label: '配置', type: 'label' },
    { label: '插件设置', icon: 'i-lucide-settings-2', to: '/settings' },
    { label: '管理员', icon: 'i-lucide-shield-user', to: '/admins' },
    { label: '审计日志', icon: 'i-lucide-scroll-text', to: '/audit' },
  ],
]

async function signOut() {
  const { error } = await logout()
  if (error) {
    toast.add({ title: '退出登录失败', description: errorMessage(error), color: 'error' })
    return
  }
  me.value = null
  await navigateTo('/login')
}

const userMenu = computed<DropdownMenuItem[][]>(() => [
  [{ type: 'label', label: me.value?.name || me.value?.login }],
  [{ label: '退出登录', icon: 'i-lucide-log-out', onSelect: signOut }],
])
</script>

<template>
  <UDashboardGroup>
    <UDashboardSidebar
      id="main"
      collapsible
      resizable
      :ui="{ footer: 'border-t border-default' }"
    >
      <template #header="{ collapsed }">
        <div class="flex w-full items-center gap-2 px-1">
          <UIcon name="i-lucide-bot" class="size-5 shrink-0 text-primary" />
          <span v-if="!collapsed" class="truncate font-semibold">BotFooChan</span>
        </div>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="nav"
          orientation="vertical"
          tooltip
        />
      </template>

      <template #footer="{ collapsed }">
        <div class="flex w-full items-center gap-1">
          <UDropdownMenu
            v-if="me"
            :items="userMenu"
            :content="{ align: 'center', collisionPadding: 12 }"
            class="min-w-0 flex-1"
          >
            <UButton
              :avatar="{ src: me.avatar_url || undefined, alt: me.login }"
              :label="collapsed ? undefined : me.login"
              :trailing-icon="collapsed ? undefined : 'i-lucide-chevrons-up-down'"
              :square="collapsed"
              color="neutral"
              variant="ghost"
              block
              class="data-[state=open]:bg-elevated"
              :ui="{ trailingIcon: 'ms-auto text-dimmed' }"
            />
          </UDropdownMenu>
          <UColorModeButton v-if="!collapsed" />
        </div>
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>
