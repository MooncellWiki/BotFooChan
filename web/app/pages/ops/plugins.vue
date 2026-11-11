<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { listPluginsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading } = useQuery(listPluginsQuery())
const search = ref('')
const shown = computed(() => {
  const q = search.value.trim().toLowerCase()
  return (data.value ?? []).filter(p => !q || [p.id, p.name, p.description].some(s => s.toLowerCase().includes(q)))
})
</script>

<template>
  <AppPage title="插件" description="已加载的插件和它们注册的事件响应器（只读）。">
    <template #actions>
      <UInput v-model="search" placeholder="搜索插件" icon="i-lucide-search" class="w-56" />
    </template>
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />
    <p v-if="data" class="text-xs text-muted">
      共 {{ data.length }} 个，事件响应器 {{ data.reduce((n, p) => n + p.matchers.length, 0) }} 个
    </p>
    <div class="grid gap-3 lg:grid-cols-2">
      <UCard v-for="plugin in shown" :key="plugin.id" :ui="{ body: 'sm:p-4' }">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="font-medium">
              {{ plugin.name }}
            </p>
            <p class="truncate font-mono text-xs text-muted">
              {{ plugin.id }}<template v-if="plugin.parent">
                · 子插件
              </template>
            </p>
          </div>
          <UBadge :label="`${plugin.matchers.length} 个响应器`" color="neutral" variant="subtle" />
        </div>
        <p v-if="plugin.description" class="mt-2 text-sm text-muted">
          {{ plugin.description }}
        </p>
        <details v-if="plugin.usage || plugin.matchers.length" class="mt-2">
          <summary class="cursor-pointer text-xs text-muted">
            详情
          </summary>
          <pre v-if="plugin.usage" class="mt-2 text-xs whitespace-pre-wrap">{{ plugin.usage }}</pre>
          <ul class="mt-2 grid gap-1 text-xs">
            <li v-for="(m, i) in plugin.matchers" :key="i" class="font-mono">
              <UBadge :label="m.type || 'any'" color="neutral" variant="outline" size="sm" />
              优先级 {{ m.priority }}{{ m.block ? ' · 阻断' : '' }}
              <span v-if="m.rules.length" class="text-dimmed">· {{ m.rules.join(', ') }}</span>
            </li>
          </ul>
        </details>
      </UCard>
    </div>
  </AppPage>
</template>
