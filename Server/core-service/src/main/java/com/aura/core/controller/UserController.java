package com.aura.core.controller;

import com.aura.core.common.Response;
import com.aura.core.dto.UserDto;
import com.aura.core.service.LoginService;
import com.aura.core.util.JWTUtil;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/user")
public class UserController {

    private final LoginService loginService;
    private final JWTUtil jwtUtil;

    public UserController(LoginService loginService, JWTUtil jwtUtil) {
        this.loginService = loginService;
        this.jwtUtil = jwtUtil;
    }

    @PostMapping("register")
    public Response<UserDto> register(@Valid @RequestBody UserDto user) {
        loginService.register(user);
        return Response.ok();
    }

    @PostMapping("login")
    public Response<String> login(@Valid @RequestBody UserDto user) {
        return loginService.login(user);
    }

    @GetMapping("logout/{userId}")
    public Response<String> logout(
            @PathVariable String userId,
            @RequestHeader("Authorization") String authHeader) {
        String currentUserId = jwtUtil.getUsernameFromToken(authHeader.replace("Bearer ", ""));
        if (!currentUserId.equals(userId)) {
            return Response.error(403, "无权操作该账号");
        }
        loginService.logout(authHeader.replace("Bearer ", ""));
        return Response.ok();
    }

    @GetMapping("userInfo")
    public Response<UserDto> getUserInfo(@RequestHeader("Authorization") String authHeader) {
        UserDto info = loginService.getUserInfo(jwtUtil.getUsernameFromToken(authHeader.replace("Bearer ", "")));
        if (info == null) {
            return Response.error("用户不存在");
        }
        info.setPassword("****");
        return Response.success(info);
    }

    @PutMapping("updateInfo")
    public Response<UserDto> updateInfo(@RequestBody UserDto user) {
        loginService.updateUserInfo(user);
        return Response.ok();
    }

    @DeleteMapping("{username}")
    public Response<UserDto> deleteUser(@PathVariable String username) {
        loginService.deleteUser(username);
        return Response.ok();
    }
}
