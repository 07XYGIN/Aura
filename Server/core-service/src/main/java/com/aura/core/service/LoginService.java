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
import org.springframework.transaction.annotation.Transactional;

import java.util.concurrent.TimeUnit;

@Service
public class LoginService {
    private final UserMapper userMapper;
    private final Crypto cipher;
    private final RedisUtil redisUtil;
    private final JWTUtil jwtUtil;
    private final long jwtExpireTime;
    private final boolean inviteRegistrationRequired;

    public LoginService(
            UserMapper userMapper,
            Crypto cipher,
            RedisUtil redisUtil,
            JWTUtil jwtUtil,
            @Value("${jwt.expire-time}") long jwtExpireTime,
            @Value("${invite.registration-required:true}") boolean inviteRegistrationRequired) {
        this.userMapper = userMapper;
        this.cipher = cipher;
        this.redisUtil = redisUtil;
        this.jwtUtil = jwtUtil;
        this.jwtExpireTime = jwtExpireTime;
        this.inviteRegistrationRequired = inviteRegistrationRequired;
    }

    @Transactional
    public void register(UserDto user) {
        String inviteCode = normalizeInviteCode(user.getInviteCode());
        if (inviteRegistrationRequired && inviteCode == null) {
            throw new IllegalArgumentException("邀请码不能为空");
        }

        if (inviteCode != null && userMapper.countAvailableInviteCode(inviteCode) <= 0) {
            throw new IllegalArgumentException("邀请码无效或已过期");
        }

        user.setPassword(cipher.encodedPassword(user.getPassword()));
        userMapper.insertUser(user);

        if (inviteCode == null) {
            return;
        }

        String userId = userMapper.findUserIdByUsername(user.getUsername());
        if (userId == null || userId.isBlank()) {
            throw new IllegalStateException("用户注册状态异常");
        }

        int consumed = userMapper.consumeInviteCode(inviteCode, userId);
        if (consumed <= 0) {
            throw new IllegalArgumentException("邀请码已被使用，请换一个邀请码");
        }
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

    private String normalizeInviteCode(String inviteCode) {
        if (inviteCode == null || inviteCode.isBlank()) {
            return null;
        }
        return inviteCode.trim().toUpperCase();
    }
}
