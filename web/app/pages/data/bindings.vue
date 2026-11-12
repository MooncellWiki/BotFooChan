<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { GroupBindingOut } from '~/client'
import { deleteBinding } from '~/client'
import { listBindingsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listBindingsQuery())
const { run } = useAction()

async function remove(binding: GroupBindingOut) {
  if (await run(() => deleteBinding({ path: { group_id: binding.group_id }, throwOnError: true }), `已删除群 ${binding.group_id} 的绑定`)) await refetch()
}

const columns: TableColumn<GroupBindingOut>[] = [
  { accessorKey: 'group_id', header: '群号' },
  { accessorKey: 'group_openid', header: 'group_openid' },
  { accessorKey: 'online', header: '官方机器人' },
  { accessorKey: 'fgo_push', header: 'FGO 维护推送' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="群号绑定" description="群号和 QQ 官方机器人 group_openid 的对应，外部推送和按群号存的订阅都靠它。新增要在群里 @ 官方机器人发 /官q 绑定 <群号>。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-48" />
    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data" :columns="columns" empty="还没有绑定">
        <template #group_id-cell="{ row }">
          <span class="font-mono">{{ row.original.group_id }}</span>
        </template>
        <template #group_openid-cell="{ row }">
          <code class="text-xs">{{ row.original.group_openid }}</code>
        </template>
        <template #online-cell="{ row }">
          <UBadge v-if="row.original.online" label="在线" color="success" variant="subtle" icon="i-lucide-circle-check" />
          <UBadge v-else label="不在线" color="warning" variant="subtle" icon="i-lucide-triangle-alert" />
          <span v-if="row.original.bot_id" class="ms-1 font-mono text-xs text-dimmed">{{ row.original.bot_id }}</span>
        </template>
        <template #fgo_push-cell="{ row }">
          <UIcon v-if="row.original.fgo_push" name="i-lucide-check" class="text-success" />
          <span v-else class="text-dimmed">—</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end">
            <ConfirmButton :message="`删除群 ${row.original.group_id} 的绑定？之后发往这个群号的推送都会失败。`" @confirm="remove(row.original)" />
          </div>
        </template>
      </UTable>
    </UCard>
  </AppPage>
</template>
