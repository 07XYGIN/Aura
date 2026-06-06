<template>
  <div v-if="props.loading" class="grid grid-cols-4 gap-4">
    <template v-for="item in 10" :key="item">
      <Skeleton class="h-60 w-60" />
    </template>
  </div>
  <div v-else-if="props.memory && props.memory.length === 0">
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FolderOpen />
        </EmptyMedia>
      </EmptyHeader>
      <EmptyTitle>No memories yet</EmptyTitle>
    </Empty>
  </div>
  <div v-else class="grid grid-cols-4 gap-4">
    <div v-for="item in props.memory" :key="item.id" class="group">
      <Card class="transition-all duration-300 hover:border-gray-400 hover:shadow-lg">
        <CardHeader class="flex items-center justify-between pb-2">
          <Badge variant="secondary" class="text-xs">
            {{ item.metadata.title }}
          </Badge>
          <span class="text-muted-foreground font-mono text-[10px]">
            {{ item.metadata.create_time }}
          </span>
        </CardHeader>

        <CardContent class="line-clamp-4 p-2 text-sm leading-relaxed text-zinc-300">
          <span>{{ item.metadata.content }}</span>
        </CardContent>

        <CardFooter class="flex justify-end opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <Button variant="ghost" size="sm" class="cursor-pointer" @click="delData(item.id)">
            <Trash color="#ef4444" />
          </Button>
        </CardFooter>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FolderOpen, Trash } from 'lucide-vue-next';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '../ui/card';
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle } from '../ui/empty';
import { Skeleton } from '../ui/skeleton';

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

const props = defineProps<{
  memory: MemoryDocument[];
  loading: boolean;
}>();

const emit = defineEmits<{
  delData: [id: string];
}>();

const delData = (id: string) => {
  emit('delData', id);
};
</script>
