<template>
  <div class="flex h-full w-full flex-col px-16">
    <div ref="msgContainer" class="flex-1 overflow-auto">
      <div
        v-for="(item, index) in msgRes"
        :key="index"
        class="p-2"
        :class="item.type === 'human' ? 'text-right' : 'text-left'"
      >
        <div>{{ item.content }}</div>
      </div>
    </div>
    <div class="sticky bottom-0 z-10">
      <div class="bg-background mt-4">
        <div class="grid gap-6">
          <InputGroup>
            <InputGroupTextarea placeholder="Send a message to Aura" v-model="msg" @keydown.enter.prevent="send" />
            <InputGroupAddon align="block-end">
              <InputGroupText class="ml-auto" />
              <InputGroupButton
                variant="default"
                class="rounded-full"
                size="icon-xs"
                @click="isSend ? cancel() : send()"
              >
                <ArrowUpIcon v-if="!isSend" class="size-4" />
                <Loader v-else class="size-4 animate-spin" stroke="red" />
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowUpIcon, Loader } from 'lucide-vue-next';
import { onMounted, ref } from 'vue';

import { getMsgList } from '../api/msg';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupText,
  InputGroupTextarea,
} from '../components/ui/input-group';
import useUserStore from '../store/modules';
import useSse from '../utils/useSse';

const msg = ref('');
const msgContainer = ref<HTMLDivElement | null>(null);
const userStore = useUserStore();
const msgRes = ref<Array<{ type: string; content: string }>>([]);
const isSend = ref(false);
const chatSseUrl = `${import.meta.env.VITE_BFF_URL || 'http://127.0.0.1:3001'}/api/chat/sse`;

const mapHistoryMessage = (item: { content?: string; senderType?: string; role?: string }) => {
  const role = item.senderType ?? item.role;
  return {
    type: role === 'user' || role === 'human' ? 'human' : 'ai',
    content: item.content ?? '',
  };
};

const { connect, disconnect } = useSse(chatSseUrl, {
  headers: userStore.getCode() ? { Authorization: `Bearer ${userStore.getCode()}` } : undefined,
  onMessage: (data) => {
    if (data === '[DONE]') {
      isSend.value = false;
      getList();
      return;
    }
    let content = data;

    try {
      const parsed = JSON.parse(data) as { content?: string; event?: string };
      content = parsed.content ?? '';
    } catch {
      content = data;
    }

    if (!content) return;

    const lastMsg = msgRes.value[msgRes.value.length - 1];
    if (lastMsg?.type === 'ai') {
      lastMsg.content += content;
    } else {
      msgRes.value.push({ type: 'ai', content });
    }
    scrollToBottom();
  },
  onError: () => {
    isSend.value = false;
  },
  onClose: () => {
    isSend.value = false;
  },
});

const send = async () => {
  if (isSend.value || !msg.value.trim()) return;

  isSend.value = true;
  const content = msg.value;
  msg.value = '';
  msgRes.value.push({ type: 'human', content });
  msgRes.value.push({ type: 'ai', content: '' });
  await connect({
    body: JSON.stringify({
      message: content,
      clientMessageId: `pc-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    }),
  });
  scrollToBottom();
};

const getList = async () => {
  if (userStore.userinfo.userId) {
    const { data } = await getMsgList(userStore.userinfo.userId);
    msgRes.value = Array.isArray(data) ? data.map(mapHistoryMessage).filter((item) => item.content) : [];
  }
};

const cancel = () => {
  isSend.value = false;
  disconnect();
};

const scrollToBottom = () => {
  if (msgContainer.value) {
    msgContainer.value.scrollTo({
      top: msgContainer.value.scrollHeight,
      behavior: 'smooth',
    });
  }
};

onMounted(async () => {
  await userStore.UserInfo();
  await getList();
  scrollToBottom();
});
</script>
