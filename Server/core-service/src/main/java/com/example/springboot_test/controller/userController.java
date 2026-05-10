package com.example.springboot_test.controller;

import com.example.springboot_test.common.Response;
import com.example.springboot_test.DTO.UserDto;
import com.example.springboot_test.service.LoginService;
import com.example.springboot_test.util.JWTUtil;
import com.example.springboot_test.util.RedisUtil;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/user")
@CrossOrigin

public class userController {
    private final LoginService loginService;
    private final RedisUtil redisUtil;
    private final JWTUtil jWTUtil;

    public userController(LoginService loginService, RedisUtil redisUtil, JWTUtil jWTUtil) {
        this.loginService = loginService;
        this.redisUtil = redisUtil;
        this.jWTUtil = jWTUtil;
    }


    @PostMapping("register")
    public Response<UserDto> register(@Valid @RequestBody UserDto user) {
        loginService.register(user);
        return Response.ok();
    }

    @PostMapping("Login")
    public Response<String> Login(@Valid @RequestBody UserDto user) {
        return loginService.Login(user);
    }

    @GetMapping("logout/{userId}")
    public Response<String> Logout(@Valid @PathVariable String userId){
        loginService.Logout(userId);
        return Response.ok();
    }

    @GetMapping("userInfo")
    public Response<UserDto> GetUserInfo(@RequestHeader("Authorization") String authHeader){
        UserDto info = loginService.GetUserInfoService(jWTUtil.getUsernameFromToken(authHeader.replace("Bearer ", "")));
        if(info == null){
            return Response.Error("用户不存在");
        }
        info.setPassword("****");
        return Response.Success(info);
    }

    @PutMapping("updateInfo")
    public Response<UserDto> updateInfo (@RequestBody UserDto user){
        loginService.upDateUserInfoService(user);
        return Response.ok();
    }

    @DeleteMapping("deleteuser/{username}")
    public Response<UserDto> logoutUser(@Valid @PathVariable String username){
        loginService.LogoutUser(username);
        return Response.ok();
    }
}
