package com.aura.core.service;

import com.aura.core.common.Response;
import com.aura.core.dto.UserDto;
import com.aura.core.entity.Users;
import com.aura.core.mapper.UserMapper;
import com.aura.core.util.Crypto;
import com.aura.core.util.JWTUtil;
import com.aura.core.util.RedisUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Service
public class LoginService {
    private final UserMapper userMapper;
    private final Crypto cipher;
    private final RedisUtil redisUtil;
    private final JWTUtil jwtUtil;
    private final long jwtExpireTime;

    public LoginService(
            UserMapper userMapper,
            Crypto cipher,
            RedisUtil redisUtil,
            JWTUtil jwtUtil,
            @Value("${jwt.expire-time}") long jwtExpireTime) {
        this.userMapper = userMapper;
        this.cipher = cipher;
        this.redisUtil = redisUtil;
        this.jwtUtil = jwtUtil;
        this.jwtExpireTime = jwtExpireTime;
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
        return Response.loginSuccess(token);
    }

    public void logout(String token) {
        redisUtil.set(
                "revoked_token:" + token,
                "1",
                jwtExpireTime,
                TimeUnit.MILLISECONDS
        );
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
