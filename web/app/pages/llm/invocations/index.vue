<script setup lang="ts">
import type { BadgeProps, TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { InvocationSummary } from '~/client'
import { getInvocationFiltersQuery, listInvocationsQuery } from '~/client/@pinia/colada.gen'

const PAGE_SIZE = 30
const ALL = '__all__'
const route = useRoute()
const router = useRouter()

const task = ref(typeof route.query.task === 'string' ? route.query.task : ALL)
const status = ref(ALL)
const model = ref(ALL)
const session = ref('')
const page = ref(1)
watch([task, status, model, session], () => {
  page.value = 1
  router.replace({ query: task.value === ALL ? {} : { task: task.value } })
})

const filters = useQuery(getInvocationFiltersQuery())
const { data, error, isLoading } = useQuery(() => listInvocationsQuery({
  query: {
    task: task.value === ALL ? undefined : task.value,
    status: status.value === ALL ? undefined : status.value,
    model: model.value === ALL ? undefined : model.value,
    session: session.value.trim() || undefined,
    limit: PAGE_SIZE,
    offset: (page.value - 1) * PAGE_SIZE,
  },
}))

const options = (values: string[] | undefined, allLabel: string) => [
  { label: allLabel, value: ALL },
  ...(values ?? []).map(v => ({ label: v, value: v })),
]
const statusItems = [
  { label: '全部状态', value: ALL },
  { label: '成功', value: 'ok' },
  { label: '失败', value: 'error' },
  { label: '取消', value: 'cancelled' },
]

const STATUS: Record<string, { label: string, color: BadgeProps['color'], icon: string }> = {
  ok: { label: '成功', color: 'success', icon: 'i-lucide-circle-check' },
  error: { label: '失败', color: 'error', icon: 'i-lucide-circle-alert' },
  cancelled: { label: '取消', color: 'neutral', icon: 'i-lucide-circle-slash' },
}

const columns: TableColumn<InvocationSummary>[] = [
  { accessorKey: 'created_at', header: '时间' },
  { accessorKey: 'task', header: '功能' },
  { accessorKey: 'model_alias', header: '模型' },
  { accessorKey: 'status', header: '状态' },
  { accessorKey: 'latency_ms', header: '耗时' },
  { accessorKey: 'input_tokens', header: 'token（入 / 出）' },
  { accessorKey: 'output_preview', header: '回答' },
]
</script>

<template>
  <AppPage title="调用记录" description="每次模型调用的用量、耗时和对话内容。内容默认保留 30 天、记录保留 180 天，可在「插件设置 · 调用记录」里改。">
    <div class="flex flex-wrap gap-2">
      <USelect v-model="task" :items="options(filters.data.value?.tasks, '全部功能')" class="w-40" />
      <USelect v-model="model" :items="options(filters.data.value?.models, '全部模型')" class="w-52" />
      <USelect v-model="status" :items="statusItems" class="w-32" />
      <UInput v-model="session" placeholder="会话 id" icon="i-lucide-search" class="w-56" />
    </div>

    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />

    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data.items" :columns="columns" empty="没有记录" class="cursor-pointer" @select="(_e: Event, row: { original: InvocationSummary }) => navigateTo(`/llm/invocations/${row.original.id}`)">
        <template #created_at-cell="{ row }">
          <span class="whitespace-nowrap text-xs">{{ formatDateTime(row.original.created_at) }}</span>
        </template>
        <template #task-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.task }}</span>
          <p v-if="row.original.session_id" class="max-w-48 truncate text-[11px] text-dimmed" :title="row.original.session_id">
            {{ row.original.session_id }}
          </p>
        </template>
        <template #model_alias-cell="{ row }">
          <span class="text-xs">{{ row.original.model_alias ?? row.original.model_name }}</span>
          <UBadge v-if="row.original.web_search" label="联网" color="neutral" variant="subtle" size="sm" class="ms-1" />
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :label="STATUS[row.original.status]?.label ?? row.original.status"
            :icon="STATUS[row.original.status]?.icon"
            :color="STATUS[row.original.status]?.color ?? 'neutral'"
            variant="subtle"
          />
        </template>
        <template #latency_ms-cell="{ row }">
          <span class="font-mono text-xs">{{ (row.original.latency_ms / 1000).toFixed(1) }}s</span>
        </template>
        <template #input_tokens-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.input_tokens.toLocaleString() }} / {{ row.original.output_tokens.toLocaleString() }}</span>
          <span v-if="row.original.tool_calls" class="ms-1 text-[11px] text-dimmed">工具 {{ row.original.tool_calls }}</span>
        </template>
        <template #output_preview-cell="{ row }">
          <p class="line-clamp-2 max-w-md whitespace-normal text-xs" :class="row.original.status === 'ok' ? '' : 'text-muted'">
            {{ row.original.status === 'ok' ? row.original.output_preview : row.original.error }}
          </p>
        </template>
      </UTable>
      <template #footer>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span class="text-xs text-muted">共 {{ data.total }} 条</span>
          <UPagination v-model:page="page" :total="data.total" :items-per-page="PAGE_SIZE" :sibling-count="1" :show-edges="false" size="sm" />
        </div>
      </template>
    </UCard>
  </AppPage>
</template>
