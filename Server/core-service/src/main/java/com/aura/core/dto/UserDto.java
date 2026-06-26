package com.aura.core.dto;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.util.UUID;

@Data
public class UserDto {

    @NotNull(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    @Email(message = "邮箱格式不正确")
    private String email;

    private Integer age;

    @Min(value = 0, message = "性别只允许女(0)或男(1)")
    @Max(value = 1, message = "性别只允许女(0)或男(1)")
    private Integer sex;

    private String id;

    private String inviteCode;
}
