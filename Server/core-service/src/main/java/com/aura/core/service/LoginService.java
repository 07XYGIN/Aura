package com.aura.core.service;

import com.aura.core.common.Response;
import com.aura.core.dto.UserDto;
import com.aura.core.entity.Users;
import com.aura.core.mapper.UserMapper;
import com.aura.core.util.Crypto;
import com.aura.core.util.JWTUtil;
import com.aura.core.util.RedisUtil;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Service
public class LoginService {
    private final UserMapper userMapper;
    private final Crypto cipher;
    private final RedisUtil redisUtil;
    private final JWTUtil jwtUtil;

    public LoginService(UserMapper userMapper, Crypto cipher, RedisUtil redisUtil, JWTUtil jwtUtil) {
        this.userMapper = userMapper;
        this.cipher = cipher;
        this.redisUtil = redisUtil;
        this.jwtUtil = jwtUtil;
    }

    public void register(UserDto user) {
        user.setPassword(cipher.encodedPassword(user.getPassword()));
        userMapper.insertUser(user);
    }

    public Response<String> login(UserDto user) {
        Users userinfo = userMapper.findUser(user);
        if (userinfo == null) {
            return Response.error("用户不存在");
        }
        if (!cipher.matches(user.getPassword(), userinfo.getPassword())) {
            return Response.error("密码错误");
        }
        String token = jwtUtil.generateToken(userinfo.getId());
        redisUtil.set(
                "token:" + userinfo.getId(),
                token,
                24,
                TimeUnit.HOURS
        );
        return Response.loginSuccess(token);
    }

    public void logout(String userId) {
        redisUtil.delete("token:" + userId);
    }

    public UserDto getUserInfo(String userId) {
        return userMapper.findUserInfo(userId);
    }

    public void updateUserInfo(UserDto user) {
        userMapper.updateUser(user);
    }

    public void deleteUser(String username) {
        userMapper.deleteUser(username);
    }
}
