<template>
  <ReadOnlyResourcePage :config="auraRelationshipConfig" />
</template>

<script setup lang="ts">
import ReadOnlyResourcePage from './ReadOnlyResourcePage.vue'
import { auraRelationshipConfig } from './resourceConfig'
</script>
