<script setup lang="ts">
defineProps<{ title: string, description?: string }>()
</script>

<template>
  <!-- Keep content at its natural height; the panel body owns vertical scrolling. -->
  <UDashboardPanel :id="title" :ui="{ body: 'min-h-0 [&>*]:shrink-0 [&>*]:min-w-0 [&>*]:max-w-full' }">
    <template #header>
      <UDashboardNavbar
        :title="title"
        :ui="{
          root: 'h-auto min-h-(--ui-header-height) flex-wrap py-2',
          right: 'max-w-full flex-wrap',
        }"
      >
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <slot name="actions" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <p v-if="description" class="-mt-2 text-sm text-muted">
        {{ description }}
      </p>
      <slot />
    </template>
  </UDashboardPanel>
</template>
