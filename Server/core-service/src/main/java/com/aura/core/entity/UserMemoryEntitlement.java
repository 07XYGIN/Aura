package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UserMemoryEntitlement {
    private String userId;
    private Boolean permanentMemory;
    private OffsetDateTime expiresAt;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
