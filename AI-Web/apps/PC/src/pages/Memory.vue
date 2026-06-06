<template>
  <div class="p-5">
    <MemoryList :memory="memoryList" :loading="loading" @del-data="deleteMemory" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { deleteMemoryItem, getMemoryList } from '../api/msg';
import MemoryList from '../components/pages/MemoryList.vue';
import useUserStore from '../store/modules';

export interface MemoryMetadata {
  title: string;
  content: string;
  create_time: string;
  timestamp: string;
}

export interface MemoryDocument {
  id: string;
  metadata: MemoryMetadata;
  page_content: string;
  type: 'Document';
}

const userStore = useUserStore();
const loading = ref(false);
const memoryList = ref<MemoryDocument[]>([]);

const loadMemory = async () => {
  if (!userStore.userinfo.userId) return;

  try {
    loading.value = true;
    const { data } = await getMemoryList({ user_id: userStore.userinfo.userId });
    memoryList.value = data;
  } finally {
    loading.value = false;
  }
};

const deleteMemory = async (id: string) => {
  if (!userStore.userinfo.userId) return;

  try {
    loading.value = true;
    await deleteMemoryItem(userStore.userinfo.userId, id);
    await loadMemory();
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  await userStore.UserInfo();
  await loadMemory();
});
</script>
