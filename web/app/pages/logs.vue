<script setup lang="ts">
import type { LogLine } from '~/client'
import { getLogs } from '~/client'

const MAX_LINES = 2000
const POLL_INTERVAL = 2000
const LEVELS = ['INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'] as const
const RANK: Record<string, number> = { INFO: 20, SUCCESS: 25, WARNING: 30, ERROR: 40, CRITICAL: 50 }
const COLOR: Record<string, string> = { SUCCESS: 'text-success', WARNING: 'text-warning', ERROR: 'text-error', CRITICAL: 'text-error font-semibold' }

const lines = ref<LogLine[]>([])
const lastId = ref(0)
const level = ref<(typeof LEVELS)[number]>('INFO')
const search = ref('')
const paused = ref(false)
const follow = ref(true)
const failed = ref('')
const box = ref<HTMLElement | null>(null)

async function poll() {
  if (paused.value) return
  const { data, error } = await getLogs({ query: { after: lastId.value, limit: 2000 } })
  if (error || !data) {
    failed.value = errorMessage(error)
    return
  }
  failed.value = ''
  lastId.value = data.last_id
  if (!data.items.length) return
  lines.value = [...lines.value, ...data.items].slice(-MAX_LINES)
  if (follow.value) {
    await nextTick()
    box.value?.scrollTo({ top: box.value.scrollHeight })
  }
}

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  poll()
  timer = setInterval(poll, POLL_INTERVAL)
})
onBeforeUnmount(() => clearInterval(timer))

const shown = computed(() => {
  const minimum = RANK[level.value] ?? 0
  const q = search.value.trim().toLowerCase()
  return lines.value.filter(l => (RANK[l.level] ?? 0) >= minimum && (!q || l.message.toLowerCase().includes(q) || l.name.toLowerCase().includes(q)))
})
</script>

<template>
  <AppPage title="日志" description="最近 2000 条 INFO 及以上的日志，每 2 秒刷新；只在内存里，重启后清空。">
    <template #actions>
      <UButton :label="paused ? '继续' : '暂停'" :icon="paused ? 'i-lucide-play' : 'i-lucide-pause'" color="neutral" variant="ghost" @click="paused = !paused" />
      <UButton label="清屏" icon="i-lucide-eraser" color="neutral" variant="ghost" @click="lines = []" />
    </template>

    <div class="flex flex-wrap items-center gap-2">
      <USelect v-model="level" :items="[...LEVELS]" class="w-36" />
      <UInput v-model="search" placeholder="搜索" icon="i-lucide-search" class="w-64" />
      <USwitch v-model="follow" label="自动滚到底" />
      <span class="ms-auto text-xs text-muted">{{ shown.length }} / {{ lines.length }} 条</span>
    </div>
    <UAlert v-if="failed" color="error" variant="subtle" title="拉取失败" :description="failed" />

    <div ref="box" class="h-[calc(100svh-15rem)] min-h-80 overflow-auto rounded-md border border-default bg-elevated/40 p-3 font-mono text-xs leading-relaxed">
      <p v-if="!shown.length" class="text-muted">
        暂无日志
      </p>
      <div v-for="line in shown" :key="line.id" class="whitespace-pre-wrap break-all">
        <span class="text-dimmed">{{ formatTime(line.time) }}</span>
        <span class="mx-1.5" :class="COLOR[line.level] ?? 'text-muted'">{{ line.level.padEnd(7) }}</span>
        <span class="text-primary/80">{{ line.name }}</span>
        <span class="text-dimmed"> | </span>
        <span :class="COLOR[line.level]">{{ line.message }}</span>
      </div>
    </div>
  </AppPage>
</template>
