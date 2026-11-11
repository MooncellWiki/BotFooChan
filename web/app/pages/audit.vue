<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { AuditEntry } from '~/client'
import { listAuditQuery } from '~/client/@pinia/colada.gen'

const PAGE_SIZE = 30
const page = ref(1)
const ALL = '__all__'
const entity = ref(ALL)
const entityItems = [
  { label: '全部', value: ALL },
  { label: '配置', value: 'settings:' },
  { label: '管理员', value: 'admin' },
]
watch(entity, () => (page.value = 1))

const { data, error, isLoading } = useQuery(() => listAuditQuery({
  query: { entity: entity.value === ALL ? undefined : entity.value, limit: PAGE_SIZE, offset: (page.value - 1) * PAGE_SIZE },
}))

function changes(entry: AuditEntry): [string, unknown[]][] {
  const value = entry.detail.changes
  return isPlainObject(value) ? Object.entries(value as Record<string, unknown[]>) : []
}

function brief(value: unknown): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text === undefined ? '—' : text.length > 80 ? `${text.slice(0, 80)}…` : text
}

const columns: TableColumn<AuditEntry>[] = [
  { accessorKey: 'at', header: '时间' },
  { accessorKey: 'actor', header: '操作人' },
  { accessorKey: 'entity', header: '对象' },
  { accessorKey: 'detail', header: '内容' },
]
</script>

<template>
  <AppPage title="审计日志" description="配置修改和后台操作的记录，密钥只记打码后的值。">
    <template #actions>
      <USelect v-model="entity" :items="entityItems" class="w-32" />
    </template>

    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />

    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data.items" :columns="columns" empty="没有记录">
        <template #at-cell="{ row }">
          <span class="whitespace-nowrap text-xs">{{ formatDateTime(row.original.at) }}</span>
        </template>
        <template #actor-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.actor }}</span>
        </template>
        <template #entity-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.entity }}</span>
          <UBadge :label="row.original.action" color="neutral" variant="subtle" size="sm" class="ms-1" />
        </template>
        <template #detail-cell="{ row }">
          <ul v-if="changes(row.original).length" class="grid max-w-xl gap-0.5 whitespace-normal text-xs">
            <li v-for="[path, [before, after]] in changes(row.original)" :key="path" class="break-all">
              <span class="font-mono">{{ path }}</span>：
              <span class="text-error line-through">{{ brief(before) }}</span>
              → <span class="text-success">{{ brief(after) }}</span>
            </li>
          </ul>
          <code v-else class="block max-w-xl whitespace-normal break-all text-xs text-muted">{{ brief(row.original.detail) }}</code>
        </template>
      </UTable>
      <template #footer>
        <div class="flex items-center justify-between">
          <span class="text-xs text-muted">共 {{ data.total }} 条</span>
          <UPagination v-model:page="page" :total="data.total" :items-per-page="PAGE_SIZE" size="sm" />
        </div>
      </template>
    </UCard>
  </AppPage>
</template>
