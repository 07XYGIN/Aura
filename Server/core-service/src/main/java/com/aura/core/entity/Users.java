package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class Users {
    private String id;
    private String username;
    private String password;
    private String email;
    private Short sex;
    private Integer age;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
