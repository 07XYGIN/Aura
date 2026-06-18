<script setup lang="ts">
import { reactive, ref, type HTMLAttributes } from 'vue';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Field, FieldGroup, FieldLabel, FieldDescription } from '../ui/field';
import { Input } from '../ui/input';
import type { registerForm } from '../../api/login';
import { register } from '../../api/login';
const props = defineProps<{
  class?: HTMLAttributes['class'];
}>();

const from = reactive<registerForm>({
  username: undefined,
  newPassword: undefined,
  password: '',
  code: undefined,
});
const isEqual = ref(false);
const isNum = ref(false);
const submit = async () => {
  const len = from.password?.length;
  if ((isNum.value = len < 8) || (isEqual.value = from.newPassword !== from.password)) return;
  console.log(from.password?.length == 8);
  await register(from);
};
</script>

<template>
  <div :class="cn('flex flex-col gap-6', props.class)">
    <Card class="login-card">
      <CardHeader class="text-center">
        <CardTitle class="text-xl"> Friend </CardTitle>
        <CardDescription> register </CardDescription>
      </CardHeader>
      <CardContent>
        <form>
          <FieldGroup>
            <Field>
              <FieldLabel for="checkout-7j9-card-name-43j">
                <span class="text-foreground">用户名</span>
              </FieldLabel>
              <Input placeholder="请输入用户名" required v-model="from.username" />
            </Field>
            <Field>
              <FieldLabel for="checkout-7j9-card-name-43j">
                <span class="text-foreground">密码</span>
              </FieldLabel>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                required
                v-model="from.password"
              />
              <FieldDescription>
                <span :class="!isNum ? 'text-muted-foreground' : 'text-destructive'">
                  请输入八位以上密码
                </span>
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel for="checkout-7j9-card-name-43j">
                <span class="text-foreground">重复密码</span>
              </FieldLabel>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                required
                v-model="from.newPassword"
              />
              <FieldDescription>
                <span class="text-muted-foreground"> 再次输入密码 </span>
                <p class="text-destructive my-1.5" v-if="isEqual">两次密码输入不一致</p>
              </FieldDescription>
            </Field>
            <Field>
              <Button @click="submit"> 注册 </Button>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
