package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class AdminAuditLogDto {
    private String id;
    private String adminUserId;
    private String action;
    private String targetType;
    private String targetId;
    private String detail;
    private String ipAddress;
    private OffsetDateTime createdAt;
}
