package com.example.springboot_test.Entity;

import lombok.Data;


@Data
public class Users {
    private String id;
    private String username;
    private String password;
    private String email;
    private Short sex;
    private Integer age;
}
