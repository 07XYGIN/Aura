package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class SafetyEventDto {
    private String id;
    private String userId;
    private String sessionId;
    private String messageId;
    private String riskType;
    private String riskLevel;
    private String intervention;
    private String metadata;
    private OffsetDateTime createdAt;
}
