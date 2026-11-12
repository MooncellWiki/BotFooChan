<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { addFgoGroup, removeFgoGroup } from '~/client'
import { listFgoGroupsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listFgoGroupsQuery())
const { run, pending } = useAction()
const groupId = ref('')

async function add() {
  const id = Number(groupId.value.trim())
  if (!Number.isInteger(id) || id <= 0) return
  if (await run(() => addFgoGroup({ body: { group_id: id }, throwOnError: true }), `已开启群 ${id} 的维护推送`)) {
    groupId.value = ''
    await refetch()
  }
}
async function remove(id: number) {
  if (await run(() => removeFgoGroup({ path: { group_id: id }, throwOnError: true }), `已关闭群 ${id} 的维护推送`)) await refetch()
}
</script>

<template>
  <AppPage title="FGO 维护推送" description="国服 / 日服维护状态变化时推送到这些群。推送由 QQ 官方机器人发，群号要先绑定。">
    <UCard>
      <div class="flex flex-wrap items-end gap-3">
        <UFormField label="群号">
          <UInput v-model="groupId" inputmode="numeric" placeholder="123456789" @keydown.enter="add" />
        </UFormField>
        <UButton label="开启推送" icon="i-lucide-plus" :loading="pending" :disabled="!/^\d+$/.test(groupId.trim())" @click="add" />
      </div>
    </UCard>
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-32" />
    <UCard v-if="data">
      <UEmpty v-if="!data.length" icon="i-lucide-bell-off" title="还没有群开启推送" />
      <ul class="divide-y divide-default">
        <li v-for="g in data" :key="g.group_id" class="flex items-center justify-between gap-2 py-2">
          <span class="font-mono">{{ g.group_id }}</span>
          <div class="flex items-center gap-2">
            <UBadge v-if="g.bound" label="已绑定" color="success" variant="subtle" />
            <UBadge v-else label="未绑定，推不出去" color="warning" variant="subtle" icon="i-lucide-triangle-alert" />
            <ConfirmButton :message="`关闭群 ${g.group_id} 的维护推送？`" @confirm="remove(g.group_id)" />
          </div>
        </li>
      </ul>
    </UCard>
  </AppPage>
</template>
