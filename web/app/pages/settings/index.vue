<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { listSettingsQuery } from '~/client/@pinia/colada.gen'

const { data, error, isLoading } = useQuery(listSettingsQuery())
</script>

<template>
  <AppPage title="插件设置" description="各插件的行为配置，改完立即生效（标了「重启后生效」的字段除外）。适配器、端口、数据库等基础配置仍在 .env 里。">
    <UAlert v-if="error" color="error" variant="subtle" title="加载失败" :description="errorMessage(error)" />
    <div v-if="isLoading && !data" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <USkeleton v-for="i in 6" :key="i" class="h-28" />
    </div>
    <div v-if="data" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <ULink v-for="section in data" :key="section.key" :to="`/settings/${section.key}`" class="block">
        <UCard class="h-full transition-colors hover:bg-elevated/50">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="font-semibold">
                {{ section.title }}
              </p>
              <p class="font-mono text-xs text-muted">
                {{ section.key }}
              </p>
            </div>
            <UBadge
              :label="section.source === 'database' ? '数据库' : '.env'"
              :color="section.source === 'database' ? 'primary' : 'warning'"
              variant="subtle"
            />
          </div>
          <p v-if="section.description" class="mt-2 text-sm text-muted">
            {{ section.description }}
          </p>
          <p v-if="section.updated_at" class="mt-3 text-xs text-dimmed">
            {{ section.updated_by }} · {{ formatDateTime(section.updated_at) }}
          </p>
        </UCard>
      </ULink>
    </div>
  </AppPage>
</template>
