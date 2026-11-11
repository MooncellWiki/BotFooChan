<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { getInvocationQuery } from '~/client/@pinia/colada.gen'

const route = useRoute()
const id = computed(() => Number(route.params.id))
const { data, error, isLoading } = useQuery(() => getInvocationQuery({ path: { invocation_id: id.value } }))

const SECTION: Record<string, { label: string, icon: string }> = {
  user: { label: '提问', icon: 'i-lucide-user' },
  thinking: { label: '思考', icon: 'i-lucide-brain' },
  tool: { label: '工具', icon: 'i-lucide-wrench' },
  answer: { label: '回答', icon: 'i-lucide-bot' },
  note: { label: '备注', icon: 'i-lucide-info' },
}
const str = (v: unknown) => (typeof v === 'string' ? v : '')
const sources = (v: unknown) => (Array.isArray(v) ? (v as { url: string, title?: string }[]) : [])

const facts = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    ['时间', formatDateTime(d.created_at)],
    ['功能', d.task],
    ['模型', `${d.model_alias ?? '—'}（${d.provider ?? '?'} / ${d.model_name} / ${d.api_type}）`],
    ['会话', d.session_id ?? '—'],
    ['用户', d.user_id ?? '—'],
    ['适配器', d.adapter ? `${d.adapter} ${d.bot_id ?? ''}` : '—'],
    ['耗时', `${(d.latency_ms / 1000).toFixed(2)} 秒`],
    ['token', `输入 ${d.input_tokens.toLocaleString()}（缓存 ${d.cache_read_tokens.toLocaleString()}） / 输出 ${d.output_tokens.toLocaleString()}`],
    ['请求 / 工具', `${d.requests} 次请求 · ${d.tool_calls} 次工具调用${d.web_search ? ' · 开了联网搜索' : ''}`],
  ]
})
</script>

<template>
  <AppPage :title="`调用 #${id}`">
    <template #actions>
      <UButton label="返回" icon="i-lucide-arrow-left" color="neutral" variant="ghost" @click="$router.back()" />
    </template>

    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <USkeleton v-if="isLoading && !data" class="h-64" />

    <template v-if="data">
      <UAlert
        v-if="data.status !== 'ok'"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        :title="data.status === 'cancelled' ? '调用被取消' : '调用失败'"
        :description="data.error ?? undefined"
      />
      <UCard>
        <dl class="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <template v-for="[k, v] in facts" :key="k">
            <dt class="text-muted">
              {{ k }}
            </dt>
            <dd class="break-all">
              {{ v }}
            </dd>
          </template>
        </dl>
      </UCard>

      <UAlert v-if="data.sections_error" color="warning" variant="subtle" :title="data.sections_error" />
      <UEmpty
        v-if="!data.has_messages"
        icon="i-lucide-archive"
        title="没有对话内容"
        description="过了保留期已清掉，或者记录时没开「存下对话内容」。"
      />

      <div class="grid gap-3">
        <UCard v-for="(section, i) in data.sections" :key="i" :ui="{ body: 'sm:p-4' }">
          <div class="mb-2 flex items-center gap-2 text-xs text-muted">
            <UIcon :name="SECTION[section.kind]?.icon ?? 'i-lucide-dot'" class="size-4" />
            <span class="font-medium">{{ SECTION[section.kind]?.label ?? section.kind }}</span>
            <span v-if="section.kind === 'tool'" class="font-mono">{{ str(section.data.name) }}</span>
            <span v-if="section.kind === 'note'">{{ str(section.data.label) }}</span>
          </div>
          <template v-if="section.kind === 'tool'">
            <p v-if="str(section.data.query)" class="mb-2 text-sm">
              查询：{{ str(section.data.query) }}
            </p>
            <details v-if="str(section.data.args)" class="mb-2">
              <summary class="cursor-pointer text-xs text-muted">
                参数
              </summary>
              <pre class="mt-1 max-h-64 overflow-auto rounded bg-elevated p-2 text-xs whitespace-pre-wrap">{{ str(section.data.args) }}</pre>
            </details>
            <ul v-if="sources(section.data.sources).length" class="mb-2 grid gap-1 text-xs">
              <li v-for="s in sources(section.data.sources)" :key="s.url" class="truncate">
                <a :href="safeUrl(s.url)" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">{{ s.title || s.url }}</a>
              </li>
            </ul>
            <details v-if="str(section.data.result)">
              <summary class="cursor-pointer text-xs text-muted">
                结果
              </summary>
              <pre class="mt-1 max-h-96 overflow-auto rounded bg-elevated p-2 text-xs whitespace-pre-wrap">{{ str(section.data.result) }}</pre>
            </details>
          </template>
          <pre v-else class="max-h-[32rem] overflow-auto text-sm whitespace-pre-wrap" :class="section.kind === 'thinking' ? 'text-muted' : ''">{{ str(section.data.text) }}</pre>
        </UCard>
      </div>
    </template>
  </AppPage>
</template>
