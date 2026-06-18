<script setup lang="ts">
import { reactive, ref, type HTMLAttributes } from 'vue';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Field, FieldGroup, FieldLabel } from '../ui/field';
import { useRouter } from 'vue-router';

const props = defineProps<{
  class?: HTMLAttributes['class'];
}>();
import { Input } from '../ui/input';
import type { loginForm } from '../../api/login';
import { login } from '../../api/login';
import useUserStore from '../../store/modules';
const user = useUserStore();
const router = useRouter();
const errorMessage = ref('');
const from = reactive<loginForm>({
  username: undefined,
  password: undefined,
  code: undefined,
});

const loginSubmit = async () => {
  const response = await login(from);
  const token = response?.data ?? response?.token;
  if (!token) {
    errorMessage.value = response?.message || response?.msg || '用户名、密码或邀请码错误';
    return;
  }
  errorMessage.value = '';
  user.setCode(token);
  const redirect = typeof router.currentRoute.value.query.redirect === 'string' ? router.currentRoute.value.query.redirect : '/';
  router.push(redirect);
};
</script>

<template>
  <form :class="cn('flex flex-col gap-6', props.class)">
    <FieldGroup>
      <div class="flex flex-col items-center gap-1 text-center">
        <h1 class="text-2xl">欢迎访问</h1>
        <p class="text-muted-foreground text-sm text-balance">请输入凭证验证身份</p>
      </div>
      <Field>
        <FieldLabel for="email"> 用户名 </FieldLabel>
        <Input placeholder="用户名" required v-model="from.username" />
      </Field>
      <Field>
        <div class="flex items-center">
          <FieldLabel for="password"> 密码 </FieldLabel>
        </div>
        <Input
          id="password"
          type="password"
          required
          placeholder="请输入密码"
          v-model="from.password"
        />
      </Field>
      <Field>
        <div class="flex items-center">
          <FieldLabel for="password"> 邀请码 </FieldLabel>
        </div>
        <Input
          id="password"
          type="password"
          required
          placeholder="请输入邀请码"
          v-model="from.code"
        />
      </Field>
      <Field>
        <p v-if="errorMessage" class="text-destructive text-sm">
          {{ errorMessage }}
        </p>
        <Button type="button" @click="loginSubmit"> 登录 </Button>
      </Field>
    </FieldGroup>
  </form>
</template>
