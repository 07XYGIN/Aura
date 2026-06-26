package com.aura.core.mapper;

import com.aura.core.dto.UserDto;
import com.aura.core.entity.Users;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface UserMapper {
    int insertUser(UserDto userDto);

    Users findUser(UserDto userDto);

    UserDto findUserInfo(@Param("id") String userId);

    String findUserIdByUsername(@Param("username") String username);

    int countAvailableInviteCode(@Param("code") String code);

    int consumeInviteCode(@Param("code") String code, @Param("userId") String userId);

    int deleteUser(@Param("username") String username);

    int updateUser(UserDto userDto);
}
