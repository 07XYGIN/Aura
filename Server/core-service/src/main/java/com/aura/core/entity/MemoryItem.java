package com.aura.core.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

@Data
public class MemoryItem {
    private String id;
    private String userId;
    private String auraProfileId;
    private String sourceSessionId;
    private String sourceMessageId;
    private String memoryType;
    private String title;
    private String content;
    private Integer salience;
    private BigDecimal confidence;
    private String status;
    private String tags;
    private String metadata;
    private OffsetDateTime lastRecalledAt;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
