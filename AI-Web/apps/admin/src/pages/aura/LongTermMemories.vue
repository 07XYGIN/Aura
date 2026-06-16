<template>
  <ReadOnlyResourcePage :config="auraLongTermMemoryConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraLongTermMemoryConfig } from './resourceConfig'
</script>
