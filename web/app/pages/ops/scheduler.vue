<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useQuery } from '@pinia/colada'
import type { JobInfo } from '~/client'
import { controlJob } from '~/client'
import { listJobsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading, refetch } = useQuery(listJobsQuery())
const { run } = useAction()
const busy = ref<string | null>(null)

async function act(job: JobInfo, action: 'run' | 'pause' | 'resume') {
  busy.value = job.id
  const label = { run: '已安排立即执行', pause: '已暂停', resume: '已恢复' }[action]
  const result = await run(() => controlJob({ path: { job_id: job.id, action }, throwOnError: true }), `${job.name}：${label}`)
  busy.value = null
  if (result) await refetch()
}

const columns: TableColumn<JobInfo>[] = [
  { accessorKey: 'name', header: '任务' },
  { accessorKey: 'trigger', header: '触发' },
  { accessorKey: 'next_run_time', header: '下次执行' },
  { id: 'actions', header: '' },
]
</script>

<template>
  <AppPage title="定时任务" description="apscheduler 里登记的定时任务。暂停只在这次运行期间有效，重启后按代码里的设置恢复。">
    <template #actions>
      <UButton icon="i-lucide-refresh-cw" color="neutral" variant="ghost" aria-label="刷新" @click="refetch()" />
    </template>
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-48" />
    <UCard v-if="data" :ui="{ body: 'p-0 sm:p-0' }">
      <UTable :data="data" :columns="columns" empty="没有定时任务">
        <template #name-cell="{ row }">
          <p class="font-medium">
            {{ row.original.name }}
          </p>
          <p class="max-w-md truncate font-mono text-xs text-dimmed" :title="row.original.func">
            {{ row.original.func }}
          </p>
        </template>
        <template #trigger-cell="{ row }">
          <code class="text-xs">{{ row.original.trigger }}</code>
        </template>
        <template #next_run_time-cell="{ row }">
          <span v-if="row.original.next_run_time" class="text-xs">{{ formatDateTime(row.original.next_run_time) }}</span>
          <UBadge v-else-if="row.original.pending" label="调度器未启动" color="neutral" variant="subtle" />
          <UBadge v-else label="已暂停" color="warning" variant="subtle" icon="i-lucide-pause" />
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton label="立即执行" icon="i-lucide-play" size="xs" color="neutral" variant="ghost" :loading="busy === row.original.id" @click="act(row.original, 'run')" />
            <UButton
              v-if="row.original.next_run_time"
              label="暂停"
              icon="i-lucide-pause"
              size="xs"
              color="neutral"
              variant="ghost"
              @click="act(row.original, 'pause')"
            />
            <UButton v-else label="恢复" icon="i-lucide-play-circle" size="xs" color="neutral" variant="ghost" @click="act(row.original, 'resume')" />
          </div>
        </template>
      </UTable>
    </UCard>
  </AppPage>
</template>
