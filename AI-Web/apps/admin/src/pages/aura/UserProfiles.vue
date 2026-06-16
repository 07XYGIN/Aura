<template>
  <ReadOnlyResourcePage :config="auraUserProfileConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraUserProfileConfig } from './resourceConfig'
</script>
