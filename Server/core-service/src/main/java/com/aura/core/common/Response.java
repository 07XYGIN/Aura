package com.aura.core.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

@JsonInclude(JsonInclude.Include.NON_NULL)
@Data
public class Response<T> {
    private Integer code;
    private String message;
    private String token;
    private T data;

    public static <T> Response<T> error(String message) {
        return error(400, message);
    }

    public static <T> Response<T> error(Integer code, String message) {
        Response<T> result = new Response<>();
        result.setCode(code);
        result.setMessage(message);
        return result;
    }

    public static <T> Response<T> success(T data) {
        Response<T> result = new Response<>();
        result.setCode(200);
        result.setMessage("操作成功");
        result.setData(data);
        return result;
    }

    public static <T> Response<T> ok() {
        Response<T> result = new Response<>();
        result.setCode(200);
        result.setMessage("操作成功");
        return result;
    }

    public static <T> Response<T> loginSuccess(String token) {
        Response<T> result = new Response<>();
        result.setCode(200);
        result.setMessage("操作成功");
        result.setToken(token);
        return result;
    }
}
