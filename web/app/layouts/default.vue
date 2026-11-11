<script setup lang="ts">
import type { DropdownMenuItem, NavigationMenuItem } from '@nuxt/ui'
import { logout } from '~/client'

const me = useMe()
const toast = useToast()

const nav: NavigationMenuItem[] = [
  { label: '概览', icon: 'i-lucide-gauge', to: '/' },
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
