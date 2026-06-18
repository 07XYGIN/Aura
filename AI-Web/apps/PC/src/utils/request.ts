import axios from 'axios';
import useUserStore from '../store/modules';
import router from '../router';

const BaseUrl = import.meta.env.VITE_BFF_URL || 'http://127.0.0.1:3001';
let authDialogVisible = false;

const request = axios.create({
  baseURL: BaseUrl,
});

request.interceptors.request.use(function (config) {
  const { getCode } = useUserStore();
  const token = getCode();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

request.interceptors.response.use(
  function (response) {
    if (response.data?.code === 401) {
      handleAuthExpired(response.data?.message);
      return Promise.reject(new Error(response.data?.message || 'Unauthorized'));
    }

    return response.data;
  },
  function (err) {
    console.log(err);

    if (err.response?.status === 401 || err.response?.data?.code === 401) {
      handleAuthExpired(err.response?.data?.message);
    }

    return Promise.reject(err);
  }
);

function handleAuthExpired(message?: string) {
  const userStore = useUserStore();
  userStore.clearCode();

  if (!authDialogVisible) {
    authDialogVisible = true;
    window.alert(message || '登录已过期或非法，请重新登录');
    authDialogVisible = false;
  }

  const currentRoute = router.currentRoute.value;
  if (currentRoute.name !== 'login' && currentRoute.name !== 'register') {
    router.replace({
      path: '/login',
      query: { redirect: currentRoute.fullPath },
    });
  }
}

export default request;
