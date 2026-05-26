import request from "@utils/request";

//用户登录
export const loginByJson = ( data )=>{
    return request({
    	url:'/u/loginByJson',
    	method:'post',
		data
    })
}