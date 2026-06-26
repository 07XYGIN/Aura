package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class MemoryRelationDto {
    private String id;
    private String memoryId;
    private String relationType;
    private String targetType;
    private String targetId;
    private String metadata;
    private OffsetDateTime createdAt;
}
