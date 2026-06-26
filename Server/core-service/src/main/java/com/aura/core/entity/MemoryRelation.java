package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class MemoryRelation {
    private String id;
    private String memoryId;
    private String relationType;
    private String targetType;
    private String targetId;
    private String metadata;
    private OffsetDateTime createdAt;
}
