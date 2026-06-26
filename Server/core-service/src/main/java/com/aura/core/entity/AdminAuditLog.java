package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class AdminAuditLog {
    private String id;
    private String adminUserId;
    private String action;
    private String targetType;
    private String targetId;
    private String detail;
    private String ipAddress;
    private OffsetDateTime createdAt;
}
