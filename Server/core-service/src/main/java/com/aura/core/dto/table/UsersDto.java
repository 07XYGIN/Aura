package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UsersDto {
    private String id;
    private String username;
    private String password;
    private String email;
    private Short sex;
    private Integer age;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
