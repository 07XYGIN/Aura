package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class RelationshipEvent {
    private String id;
    private String userId;
    private String relationshipStateId;
    private String eventType;
    private String title;
    private String description;
    private Integer deltaIntimacy;
    private Integer deltaTrust;
    private Integer deltaAffection;
    private Integer deltaConflict;
    private OffsetDateTime occurredAt;
    private String metadata;
    private OffsetDateTime createdAt;
}
