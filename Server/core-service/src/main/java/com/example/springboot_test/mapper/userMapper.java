package com.example.springboot_test.mapper;

import com.example.springboot_test.DTO.UserDto;
import com.example.springboot_test.Entity.Users;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface userMapper {
    int insertUser(UserDto userDto);

    Users findUser(UserDto userDto);

    UserDto findUserInfo(String username);

    int deleteUser(String username);

    int updateUser(UserDto userDto);
}

