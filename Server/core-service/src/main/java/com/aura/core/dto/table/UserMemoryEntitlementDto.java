package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UserMemoryEntitlementDto {
    private String userId;
    private Boolean permanentMemory;
    private OffsetDateTime expiresAt;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
