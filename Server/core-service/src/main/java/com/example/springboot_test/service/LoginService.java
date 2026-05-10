package com.example.springboot_test.service;

import com.example.springboot_test.DTO.UserDto;
import com.example.springboot_test.Entity.Users;
import com.example.springboot_test.common.Response;
import com.example.springboot_test.mapper.userMapper;
import com.example.springboot_test.util.Crypto;
import com.example.springboot_test.util.JWTUtil;
import com.example.springboot_test.util.RedisUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Service
public class LoginService {
    @Autowired
    private userMapper userMapper;
    @Autowired
    private Crypto cipher;
    @Autowired
    private RedisUtil redisUtil;
    @Autowired
    private JWTUtil jWTUtil;
    public void register(UserDto user){
        user.setPassword(cipher.encodedPassword(user.getPassword()));
        userMapper.insertUser(user);
    };

    public Response<String> Login(UserDto user) {
        Users userinfo = userMapper.findUser(user);
        if (userinfo == null) {
            return Response.Error("用户不存在");
        }
        if (!cipher.matches(user.getPassword(), userinfo.getPassword())) {
            return Response.Error("密码错误");
        }
        String token = jWTUtil.generateToken(userinfo.getId());
        redisUtil.set(
                "token:" + userinfo.getId(),
                token,
                24,
                TimeUnit.HOURS
        );
        return Response.loginSuccess(token);
    }


    public void Logout(String userId) {
        redisUtil.delete("token:" + userId);
    }

    public UserDto GetUserInfoService(String userId) {
        return userMapper.findUserInfo(userId);
    }

    public void upDateUserInfoService(UserDto user){
        userMapper.updateUser(user);
    }

    public void LogoutUser(String username) {
        userMapper.deleteUser(username);
    }
}
