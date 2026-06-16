<template>
  <ReadOnlyResourcePage :config="auraEmotionConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraEmotionConfig } from './resourceConfig'
</script>
