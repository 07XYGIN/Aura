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

const { connect, disconnect } = useSse('http://127.0.0.1:8000/api/send/sse/', {
  onMessage: (data) => {
    if (data === '[DONE]') {
      isSend.value = false;
      return;
    }

    const lastMsg = msgRes.value[msgRes.value.length - 1];
    if (lastMsg?.type === 'ai') {
      lastMsg.content += data;
    } else {
      msgRes.value.push({ type: 'ai', content: data });
    }
    isSend.value = false;
    scrollToBottom();
  },
  onError: () => {
    isSend.value = false;
  },
});

const send = async () => {
  if (isSend.value || !msg.value.trim()) return;

  isSend.value = true;
  msgRes.value.push({ type: 'human', content: msg.value });
  await connect({
    body: JSON.stringify({
      message: msg.value,
      userId: userStore.userinfo.userId,
    }),
  });
  msg.value = '';
  scrollToBottom();
};

const getList = async () => {
  if (userStore.userinfo.userId) {
    const { data } = await getMsgList(userStore.userinfo.userId);
    msgRes.value = data;
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
