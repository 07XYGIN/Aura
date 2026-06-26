package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class RelationshipStateDto {
    private String id;
    private String userId;
    private String auraProfileId;
    private String relationshipStage;
    private Integer intimacyLevel;
    private Integer trustLevel;
    private Integer affectionLevel;
    private Integer conflictLevel;
    private String currentMood;
    private OffsetDateTime lastInteractionAt;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
