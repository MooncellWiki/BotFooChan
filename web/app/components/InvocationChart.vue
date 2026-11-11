<script setup lang="ts">
import type { DailyStat } from '~/client'

const props = defineProps<{ days: DailyStat[] }>()
const showTable = ref(false)

// 纵轴取一个整齐的上限：1 / 2 / 5 × 10^n
function niceMax(value: number): number {
  const power = 10 ** Math.floor(Math.log10(Math.max(value, 1)))
  const step = [1, 2, 5, 10].find(s => s * power >= value) ?? 10
  return step * power
}
const max = computed(() => niceMax(Math.max(...props.days.map(d => d.ok + d.error), 1)))
const ticks = computed(() => [max.value, max.value / 2, 0])
const CHART_HEIGHT = 160 // 和下面的 h-40 一致
const px = (n: number) => `${Math.max(2, (n / max.value) * CHART_HEIGHT)}px`
const shortDate = (date: string) => date.slice(5)
const label = (d: DailyStat) => `${d.date}：成功 ${d.ok} 次，失败 ${d.error} 次，token ${(d.input_tokens + d.output_tokens).toLocaleString()}`
</script>

<template>
  <div class="invocation-chart">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs">
      <div class="flex items-center gap-4 text-muted">
        <span class="flex items-center gap-1.5"><span class="swatch ok" />成功</span>
        <span class="flex items-center gap-1.5"><span class="swatch error" /><UIcon name="i-lucide-circle-alert" class="size-3.5" />失败</span>
      </div>
      <UButton
        :label="showTable ? '图表' : '表格'"
        :icon="showTable ? 'i-lucide-chart-column' : 'i-lucide-table'"
        size="xs"
        color="neutral"
        variant="ghost"
        @click="showTable = !showTable"
      />
    </div>

    <table v-if="showTable" class="w-full text-xs">
      <thead class="text-muted">
        <tr>
          <th class="py-1 text-left font-normal">
            日期
          </th>
          <th class="py-1 text-right font-normal">
            成功
          </th>
          <th class="py-1 text-right font-normal">
            失败
          </th>
          <th class="py-1 text-right font-normal">
            token
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in [...days].reverse()" :key="d.date" class="border-t border-default">
          <td class="py-1">
            {{ d.date }}
          </td>
          <td class="py-1 text-right font-mono">
            {{ d.ok }}
          </td>
          <td class="py-1 text-right font-mono">
            {{ d.error }}
          </td>
          <td class="py-1 text-right font-mono">
            {{ (d.input_tokens + d.output_tokens).toLocaleString() }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else class="flex gap-2">
      <div class="relative h-40 w-8 shrink-0 text-right text-[10px] text-dimmed">
        <span v-for="t in ticks" :key="t" class="absolute right-0 -translate-y-1/2" :style="{ top: `${100 - (t / max) * 100}%` }">{{ t }}</span>
      </div>
      <div class="min-w-0 flex-1">
        <div class="relative h-40">
          <div
            v-for="t in ticks"
            :key="t"
            class="absolute inset-x-0 border-t border-default"
            :class="t === 0 ? '' : 'border-dashed opacity-60'"
            :style="{ top: `${100 - (t / max) * 100}%` }"
          />
          <div class="absolute inset-0 flex items-end">
            <UTooltip v-for="d in days" :key="d.date" :text="label(d)" :content="{ side: 'top' }">
              <div class="group flex h-full flex-1 items-end justify-center" tabindex="0" role="img" :aria-label="label(d)">
                <div class="flex w-full max-w-6 flex-col-reverse gap-0.5 px-0.5 group-hover:opacity-80 group-focus:opacity-80">
                  <div v-if="d.ok" class="bar ok" :class="{ top: !d.error }" :style="{ height: px(d.ok) }" />
                  <div v-if="d.error" class="bar error top" :style="{ height: px(d.error) }" />
                </div>
              </div>
            </UTooltip>
          </div>
        </div>
        <div class="mt-1 flex text-[10px] text-dimmed">
          <span v-for="(d, i) in days" :key="d.date" class="flex-1 text-center">{{ i % 2 === days.length % 2 ? '' : shortDate(d.date) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.invocation-chart {
  --series-ok: #2a78d6;
  --series-error: #d03b3b;
}
:global(.dark) .invocation-chart {
  --series-ok: #3987e5;
}
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.swatch.ok, .bar.ok {
  background: var(--series-ok);
}
.swatch.error, .bar.error {
  background: var(--series-error);
}
.bar.top {
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}
</style>
