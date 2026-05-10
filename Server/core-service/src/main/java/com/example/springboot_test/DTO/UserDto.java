package com.example.springboot_test.DTO;
import jakarta.validation.constraints.*;
import lombok.Data;

@Data
public class UserDto {

    @NotNull(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    @Email(message = "邮箱格式不正确")
    private String email;

    private Integer age;

    private Integer sex;
}