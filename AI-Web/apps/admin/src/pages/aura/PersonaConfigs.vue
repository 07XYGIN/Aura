<template>
  <ReadOnlyResourcePage :config="auraPersonaConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraPersonaConfig } from './resourceConfig'
</script>
