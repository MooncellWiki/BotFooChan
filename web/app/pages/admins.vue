<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { AdminOut } from '~/client'
import { addAdmin, removeAdmin } from '~/client'
import { listAdminsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listAdminsQuery())
const { run, pending } = useAction()
const me = useMe()

const form = reactive({ login: '', note: '' })
async function add() {
  const result = await run(() => addAdmin({ body: { login: form.login.trim(), note: form.note.trim() }, throwOnError: true }), `已添加 ${form.login}`)
  if (result) {
    form.login = ''
    form.note = ''
    await refetch()
  }
}

async function remove(login: string) {
  if (await run(() => removeAdmin({ path: { login }, throwOnError: true }), `已移除 ${login}`)) await refetch()
}

const columns: TableColumn<AdminOut>[] = [
  { accessorKey: 'login', header: 'GitHub 用户名' },
  { accessorKey: 'source', header: '来源' },
  { accessorKey: 'note', header: '备注' },
  { accessorKey: 'added_at', header: '添加' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="管理员" description="能登录后台的 GitHub 账号。.env 的 WEBUI__ADMINS 里的是兜底，这里删不掉。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />

    <UCard>
      <div class="flex flex-wrap items-end gap-3">
        <UFormField label="GitHub 用户名">
          <UInput v-model="form.login" placeholder="octocat" />
        </UFormField>
        <UFormField label="备注" class="min-w-64 flex-1">
          <UInput v-model="form.note" placeholder="可选" class="w-full" />
        </UFormField>
        <UButton label="添加" icon="i-lucide-user-plus" :loading="pending" :disabled="!form.login.trim()" @click="add" />
      </div>
    </UCard>

    <USkeleton v-if="isLoading && !data" class="h-32" />
    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data" :columns="columns">
        <template #login-cell="{ row }">
          <a :href="`https://github.com/${row.original.login}`" target="_blank" rel="noopener" class="font-medium hover:underline">
            {{ row.original.login }}
          </a>
          <UBadge v-if="me?.login.toLowerCase() === row.original.login" label="你" color="primary" variant="subtle" size="sm" class="ms-2" />
        </template>
        <template #source-cell="{ row }">
          <UBadge :label="row.original.source === 'env' ? '.env' : '后台添加'" :color="row.original.source === 'env' ? 'warning' : 'neutral'" variant="subtle" />
        </template>
        <template #added_at-cell="{ row }">
          <span v-if="row.original.added_at" class="text-xs text-muted">{{ row.original.added_by }} · {{ formatDateTime(row.original.added_at) }}</span>
          <span v-else class="text-dimmed">—</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <ConfirmButton v-if="row.original.source === 'database'" :message="`移除管理员 ${row.original.login}？`" @confirm="remove(row.original.login)" />
          </div>
        </template>
      </UTable>
    </UCard>
  </AppPage>
</template>
