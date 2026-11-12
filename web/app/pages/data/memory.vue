<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { MemorySummary } from '~/client'
import { deleteMemory, getMemoryDetail, putMemory } from '~/client'
import { listMemoriesQuery } from '~/client/@pinia/colada.gen'

const PAGE_SIZE = 30
const page = ref(1)
const search = ref('')
const query = ref('')
let debounce: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    query.value = value
    page.value = 1
  }, 400)
})

const { data, error, isLoading, refetch } = useQuery(() => listMemoriesQuery({
  query: { q: query.value.trim() || undefined, limit: PAGE_SIZE, offset: (page.value - 1) * PAGE_SIZE },
}))
const { run, pending } = useAction()

const open = ref(false)
const userId = ref('')
const content = ref('')
const original = ref('')

async function view(row: MemorySummary) {
  const result = await run(() => getMemoryDetail({ path: { user_id: row.user_id }, throwOnError: true }))
  if (!result) return
  userId.value = row.user_id
  content.value = original.value = result.data.content
  open.value = true
}
async function save() {
  const result = await run(() => putMemory({ path: { user_id: userId.value }, body: { content: content.value }, throwOnError: true }), '档案已保存')
  if (result) {
    content.value = original.value = result.data.content
    await refetch()
  }
}
async function clear() {
  if (await run(() => deleteMemory({ path: { user_id: userId.value }, throwOnError: true }), '档案已清空')) {
    open.value = false
    await refetch()
  }
}

const columns: TableColumn<MemorySummary>[] = [
  { accessorKey: 'user_id', header: '用户 id' },
  { accessorKey: 'preview', header: '档案' },
  { accessorKey: 'length', header: '长度' },
  { accessorKey: 'updated_at', header: '更新' },
]
</script>

<template>
  <AppPage title="群友记忆" description="聊天时自动积累的群友档案（跨群共用）。群友自己也能用「我的记忆」「编辑记忆」「清空记忆」管理。">
    <template #actions>
      <UInput v-model="search" placeholder="搜用户 id 或内容" icon="i-lucide-search" class="w-64" />
    </template>
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />
    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data.items" :columns="columns" empty="没有档案" class="cursor-pointer" @select="(_e: Event, row: { original: MemorySummary }) => view(row.original)">
        <template #user_id-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.user_id }}</span>
        </template>
        <template #preview-cell="{ row }">
          <p class="line-clamp-2 max-w-xl whitespace-normal text-xs">
            {{ row.original.preview }}
          </p>
        </template>
        <template #length-cell="{ row }">
          <span class="font-mono text-xs">{{ row.original.length }}</span>
        </template>
        <template #updated_at-cell="{ row }">
          <span class="whitespace-nowrap text-xs">{{ formatDateTime(row.original.updated_at) }}</span>
        </template>
      </UTable>
      <template #footer>
        <div class="flex items-center justify-between">
          <span class="text-xs text-muted">共 {{ data.total }} 份</span>
          <UPagination v-model:page="page" :total="data.total" :items-per-page="PAGE_SIZE" size="sm" />
        </div>
      </template>
    </UCard>

    <UModal v-model:open="open" :title="`档案 · ${userId}`" :ui="{ content: 'sm:max-w-2xl' }">
      <template #body>
        <UTextarea v-model="content" autoresize :rows="12" :maxrows="30" class="w-full" />
        <p class="mt-2 text-xs text-muted">
          {{ content.length }} 字；超过上限时保存后会照常被压缩。
        </p>
      </template>
      <template #footer>
        <div class="flex w-full items-center justify-between gap-2">
          <ConfirmButton label="清空" :message="`清空 ${userId} 的整份档案？`" @confirm="clear" />
          <div class="flex gap-2">
            <UButton label="关闭" color="neutral" variant="ghost" @click="open = false" />
            <UButton label="保存" icon="i-lucide-save" :loading="pending" :disabled="content === original" @click="save" />
          </div>
        </div>
      </template>
    </UModal>
  </AppPage>
</template>
