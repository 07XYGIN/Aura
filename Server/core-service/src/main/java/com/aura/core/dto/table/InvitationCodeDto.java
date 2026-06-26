package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class InvitationCodeDto {
    private String id;
    private String code;
    private String batchName;
    private Integer maxUses;
    private Integer usedCount;
    private OffsetDateTime expiresAt;
    private OffsetDateTime disabledAt;
    private String createdBy;
    private String lastUsedBy;
    private OffsetDateTime lastUsedAt;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
