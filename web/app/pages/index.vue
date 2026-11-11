<script setup lang="ts">
import type { BadgeProps, TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { BotInfo, Component } from '~/client'
import { getOverviewQuery } from '~/client/@pinia/colada.gen'

const REFRESH_INTERVAL = 30_000

const { data, error, isLoading, asyncStatus, refetch } = useQuery(getOverviewQuery())

// 运行时长按当前时间算；数据刷新时顺便更新
const now = ref(Date.now())
const updatedAt = ref<number | null>(null)
watch(data, (value) => {
  if (value) {
    now.value = Date.now()
    updatedAt.value = now.value
  }
}, { immediate: true })

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => refetch(), REFRESH_INTERVAL)
})
onBeforeUnmount(() => clearInterval(timer))

const uptime = computed(() => {
  const startedAt = data.value?.started_at
  return startedAt ? formatDuration(now.value - Date.parse(startedAt)) : '—'
})

function usageColor(percent: number): BadgeProps['color'] {
  if (percent >= 90) return 'error'
  if (percent >= 70) return 'warning'
  return 'primary'
}

const STATUS: Record<Component['status'], { label: string, color: BadgeProps['color'] }> = {
  ok: { label: '正常', color: 'success' },
  error: { label: '异常', color: 'error' },
  off: { label: '未启用', color: 'neutral' },
}

const botColumns: TableColumn<BotInfo>[] = [
  { accessorKey: 'adapter', header: '适配器' },
  { accessorKey: 'self_id', header: 'ID' },
  { accessorKey: 'connected_at', header: '已连接' },
]
</script>

<template>
  <UDashboardPanel id="overview">
    <template #header>
      <UDashboardNavbar title="概览">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <span v-if="updatedAt" class="text-xs text-muted">
            更新于 {{ formatTime(updatedAt) }}
          </span>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            aria-label="刷新"
            :loading="asyncStatus === 'loading'"
            @click="refetch()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UAlert
        v-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        title="获取状态失败"
        :description="errorMessage(error)"
      />

      <div v-if="!data && isLoading" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <USkeleton v-for="i in 4" :key="i" class="h-28" />
      </div>

      <template v-if="data">
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <UCard>
            <p class="text-sm text-muted">
              版本
            </p>
            <p class="mt-1 flex items-center gap-2 text-2xl font-semibold">
              <span class="truncate">{{ data.version }}</span>
              <UBadge
                v-if="data.environment !== 'prod'"
                :label="data.environment"
                color="warning"
                variant="subtle"
              />
            </p>
            <p class="mt-2 text-xs text-muted">
              Python {{ data.python_version }} · NoneBot {{ data.nonebot_version }}
            </p>
          </UCard>

          <UCard>
            <p class="text-sm text-muted">
              运行时长
            </p>
            <p class="mt-1 text-2xl font-semibold">
              {{ uptime }}
            </p>
            <p v-if="data.started_at" class="mt-2 text-xs text-muted">
              启动于 {{ formatDateTime(data.started_at) }}
            </p>
          </UCard>

          <UCard>
            <p class="text-sm text-muted">
              CPU
            </p>
            <p class="mt-1 text-2xl font-semibold">
              {{ data.cpu_percent.toFixed(1) }}%
            </p>
            <UProgress
              class="mt-3"
              size="sm"
              :model-value="data.cpu_percent"
              :color="usageColor(data.cpu_percent)"
            />
          </UCard>

          <UCard>
            <p class="text-sm text-muted">
              内存（本进程）
            </p>
            <p class="mt-1 text-2xl font-semibold">
              {{ formatBytes(data.process_memory) }}
            </p>
            <p class="mt-2 text-xs text-muted">
              整机已用 {{ data.memory_percent.toFixed(1) }}%
            </p>
          </UCard>
        </div>

        <div class="grid gap-4 lg:grid-cols-3">
          <UCard class="lg:col-span-2" :ui="{ body: 'p-0 sm:p-0' }">
            <template #header>
              <div class="flex flex-wrap items-baseline justify-between gap-2">
                <h2 class="font-semibold">
                  在线的 bot
                </h2>
                <span class="text-xs text-muted">
                  适配器：{{ data.adapters.join('、') || '无' }} · 已加载 {{ data.plugin_count }} 个插件
                </span>
              </div>
            </template>
            <UTable :data="data.bots" :columns="botColumns" empty="没有在线的 bot">
              <template #adapter-cell="{ row }">
                <UBadge :label="row.original.adapter" color="neutral" variant="subtle" />
              </template>
              <template #self_id-cell="{ row }">
                <code class="text-xs">{{ row.original.self_id }}</code>
              </template>
              <template #connected_at-cell="{ row }">
                <span
                  v-if="row.original.connected_at"
                  :title="formatDateTime(row.original.connected_at)"
                >
                  {{ formatDuration(now - Date.parse(row.original.connected_at)) }}
                </span>
                <span v-else class="text-muted">—</span>
              </template>
            </UTable>
          </UCard>

          <UCard>
            <template #header>
              <h2 class="font-semibold">
                依赖组件
              </h2>
            </template>
            <ul class="grid gap-3">
              <li
                v-for="component in data.components"
                :key="component.name"
                class="flex items-start justify-between gap-3"
              >
                <div class="min-w-0">
                  <p class="text-sm font-medium">
                    {{ component.name }}
                  </p>
                  <p v-if="component.detail" class="break-all text-xs text-muted">
                    {{ component.detail }}
                  </p>
                </div>
                <UBadge
                  :label="STATUS[component.status].label"
                  :color="STATUS[component.status].color"
                  variant="subtle"
                />
              </li>
            </ul>
          </UCard>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
