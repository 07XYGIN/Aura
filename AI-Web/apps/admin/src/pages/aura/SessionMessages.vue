<template>
  <ReadOnlyResourcePage :config="auraMessageConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraMessageConfig } from './resourceConfig'
</script>
