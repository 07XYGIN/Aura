package com.aura.core.dto.aura;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class RelationshipStateRequest {
    private String id;
    private String auraProfileId;
    private String relationshipStage;
    private Integer intimacyLevel;
    private Integer trustLevel;
    private Integer affectionLevel;
    private Integer conflictLevel;
    private String currentMood;
    private OffsetDateTime lastInteractionAt;
    private String metadata;
}
