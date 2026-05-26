import axios from 'axios';

const request = axios.create({
    baseURL: '/api'
});

// 添加请求拦截器
request.interceptors.request.use(function (config) {
    return config;
}, function (error) {
    return Promise.reject(error);
});


// 添加响应拦截器
request.interceptors.response.use(function (response) {
    return response.data;
}, function (error) {
    return Promise.reject(error);
});

export default request;