import axios from "axios";
import {ElMessage} from "element-plus";
import { useUserStore } from "@/store/modules/user";
import router from '@/router'
const request = axios.create({
    baseURL: 'http://localhost:3000',
});

request.interceptors.request.use(function (config) {
    const userStore = useUserStore();
    if (userStore.token) {
        config.headers.Authorization = `Bearer ${userStore.token}`;
    }
    return config;
}, function (error) {
    console.error(error)
    return Promise.reject(error);
});


request.interceptors.response.use(function (response) {
    const userStore = useUserStore();
    if (response.data.code >= 200 && response.data.code < 300) {
        ElMessage.success(response.data.message);
    }
    else if(response.data.code === 401){
        ElMessage({
            message: response.data.message,
            type: 'error'
        });
        userStore.clearToken()
        router.push("/login")
    }
    else if (response.data.code >= 500 || response.data.code === 422) {
        ElMessage({
            message: response.data.message,
            type: 'error'
        });
    }else{
        ElMessage({
            message: response.data.message,
            type: 'error'
        });
    }
    return response.data;
}, function (error) {
    console.error(error)
    ElMessage.error(error.message || '请求失败');
    return Promise.reject(error);
});

export default request;
