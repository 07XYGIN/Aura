import { defineStore } from 'pinia';
import { reactive, ref } from 'vue';
import { getUserInfo } from '../../api/user';
const useUserStore = defineStore(
  'user',
  () => {
    const code = ref<string>('');
    const userinfo = reactive({
      id: undefined as string | undefined,
      createTime: undefined as string | undefined,
      userId: undefined as string | undefined,
      userName: undefined as string | undefined,
      username: undefined as string | undefined,
      email: undefined as string | undefined,
      age: undefined as number | undefined,
      sex: undefined as number | undefined,
    });
    const setCode = (co: string) => {
      code.value = co;
    };
    const clearCode = () => {
      code.value = '';
    };
    const getCode = () => {
      return code.value;
    };
    const getUserId = ()=>{
      return userinfo.userId;
    }
    const UserInfo = async () => {
      const { data } = await getUserInfo();
      userinfo.createTime = data?.createTime;
      userinfo.id = data?.id;
      userinfo.userId = data?.id ?? data?.userId;
      userinfo.userName = data?.username ?? data?.userName;
      userinfo.username = data?.username ?? data?.userName;
      userinfo.email = data?.email;
      userinfo.age = data?.age;
      userinfo.sex = data?.sex;
    };
    return {
      code,
      userinfo,
      setCode,
      clearCode,
      getCode,
      UserInfo,
      getUserId
    };
  },
  {
    persist: true,
  }
);

export default useUserStore;
