<script setup lang="ts">
import type { BadgeProps, TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { Route } from '~/client'
import { putRoute } from '~/client'
import { getLlmQuery, listRoutesQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listRoutesQuery())
const llm = useQuery(getLlmQuery())
const { run } = useAction()

const aliases = computed(() => (llm.data.value?.models ?? []).map(m => m.alias))
const saving = ref<string | null>(null)

async function change(route: Route, model: string) {
  if (model === route.value) return
  saving.value = route.id
  const result = await run(() => putRoute({
    path: { section: route.section, field: route.field },
    body: { model: model || null },
    throwOnError: true,
  }), `${route.section_title} 改用 ${model || '（不设置）'}`)
  saving.value = null
  if (result) await refetch()
}

const STATUS: Record<Route['status'], { label: string, color: BadgeProps['color'] }> = {
  ok: { label: '正常', color: 'success' },
  unset: { label: '未配置', color: 'neutral' },
  missing: { label: '别名不存在', color: 'error' },
  no_provider: { label: '服务商不存在', color: 'error' },
  no_key: { label: '缺 API Key', color: 'error' },
}

const columns: TableColumn<Route>[] = [
  { accessorKey: 'section_title', header: '功能' },
  { accessorKey: 'value', header: '模型' },
  { accessorKey: 'status', header: '状态' },
]
</script>

<template>
  <AppPage title="模型路由" description="各功能用哪个模型。选模型注册表里的别名，也可以直接输入「服务商:模型名」。改完立即生效。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-48" />
    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data" :columns="columns">
        <template #section_title-cell="{ row }">
          <p class="font-medium">
            {{ row.original.section_title }}
          </p>
          <p class="font-mono text-xs text-muted">
            {{ row.original.id }}
          </p>
          <p class="max-w-md whitespace-pre-line text-xs text-dimmed">
            {{ row.original.description }}
          </p>
        </template>
        <template #value-cell="{ row }">
          <USelectMenu
            :model-value="row.original.value ?? ''"
            :items="aliases"
            create-item
            :loading="saving === row.original.id"
            placeholder="不设置"
            class="w-64"
            @update:model-value="(v: string) => change(row.original, v)"
            @create="(v: string) => change(row.original, v)"
          />
        </template>
        <template #status-cell="{ row }">
          <UBadge :label="STATUS[row.original.status].label" :color="STATUS[row.original.status].color" variant="subtle" />
          <p class="mt-1 text-xs text-muted">
            {{ row.original.detail }}
          </p>
        </template>
      </UTable>
    </UCard>
  </AppPage>
</template>
