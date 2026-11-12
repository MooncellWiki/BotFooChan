<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { GitHubGroup, GitHubSubscription, GitHubUser } from '~/client'
import { deleteGithubSubscription, unauthGithubUser, unbindGithubGroup } from '~/client'
import { getGithubQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(getGithubQuery())
const { run } = useAction()

async function unbind(group: GitHubGroup) {
  if (await run(() => unbindGithubGroup({ path: { group_id: group.id }, throwOnError: true }), '已解除绑定')) await refetch()
}
async function unsubscribe(sub: GitHubSubscription) {
  if (await run(() => deleteGithubSubscription({ path: { subscription_id: sub.id }, throwOnError: true }), '已删除订阅')) await refetch()
}
async function unauth(user: GitHubUser) {
  if (await run(() => unauthGithubUser({ path: { user_id: user.id }, throwOnError: true }), '已撤销授权')) await refetch()
}

const groupColumns: TableColumn<GitHubGroup>[] = [
  { accessorKey: 'label', header: '群' },
  { accessorKey: 'bind_repo', header: '绑定的仓库' },
  { id: 'actions', header: '' },
]
const subColumns: TableColumn<GitHubSubscription>[] = [
  { accessorKey: 'label', header: '推送到' },
  { accessorKey: 'repo', header: '仓库' },
  { accessorKey: 'event', header: '事件' },
  { id: 'actions', header: '' },
]
const userColumns: TableColumn<GitHubUser>[] = [
  { accessorKey: 'label', header: '用户' },
  { accessorKey: 'authorized', header: '授权' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="GitHub" description="群绑定的仓库、仓库事件订阅、通过 /auth 授权过的用户（token 不显示）。新增仍在聊天里操作。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />
    <template v-if="data">
      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <template #header>
          <h2 class="font-semibold">
            群绑定
          </h2>
        </template>
        <UTable :data="data.groups" :columns="groupColumns" empty="没有群绑定仓库">
          <template #label-cell="{ row }">
            <span class="font-mono text-xs">{{ row.original.label }}</span>
          </template>
          <template #bind_repo-cell="{ row }">
            <a v-if="row.original.bind_repo" :href="`https://github.com/${row.original.bind_repo}`" target="_blank" rel="noopener" class="hover:underline">{{ row.original.bind_repo }}</a>
            <span v-else class="text-dimmed">—</span>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end">
              <ConfirmButton v-if="row.original.bind_repo" icon="i-lucide-unlink" :message="`解除 ${row.original.bind_repo} 的绑定？`" @confirm="unbind(row.original)" />
            </div>
          </template>
        </UTable>
      </UCard>

      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <template #header>
          <h2 class="font-semibold">
            仓库订阅
          </h2>
        </template>
        <UTable :data="data.subscriptions" :columns="subColumns" empty="没有订阅">
          <template #label-cell="{ row }">
            <span class="font-mono text-xs">{{ row.original.label }}</span>
          </template>
          <template #repo-cell="{ row }">
            <a :href="`https://github.com/${row.original.repo}`" target="_blank" rel="noopener" class="hover:underline">{{ row.original.repo }}</a>
          </template>
          <template #event-cell="{ row }">
            <code class="text-xs">{{ row.original.event }}</code>
            <span v-if="row.original.action?.length" class="ms-1 text-xs text-dimmed">{{ row.original.action.join(', ') }}</span>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end">
              <ConfirmButton :message="`删除对 ${row.original.repo} ${row.original.event} 的订阅？`" @confirm="unsubscribe(row.original)" />
            </div>
          </template>
        </UTable>
      </UCard>

      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <template #header>
          <h2 class="font-semibold">
            授权用户
          </h2>
        </template>
        <UTable :data="data.users" :columns="userColumns" empty="没有用户">
          <template #label-cell="{ row }">
            <span class="font-mono text-xs">{{ row.original.label }}</span>
          </template>
          <template #authorized-cell="{ row }">
            <UBadge :label="row.original.authorized ? '已授权' : '未授权'" :color="row.original.authorized ? 'success' : 'neutral'" variant="subtle" />
          </template>
          <template #actions-cell="{ row }">
            <div class="flex justify-end">
              <ConfirmButton v-if="row.original.authorized" icon="i-lucide-key-round" :message="`撤销 ${row.original.label} 的 GitHub 授权？`" @confirm="unauth(row.original)" />
            </div>
          </template>
        </UTable>
      </UCard>
    </template>
  </AppPage>
</template>
