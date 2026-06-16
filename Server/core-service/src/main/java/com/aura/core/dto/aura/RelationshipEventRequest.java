package com.aura.core.dto.aura;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class RelationshipEventRequest {
    private String relationshipStateId;

    @NotBlank(message = "eventType is required")
    private String eventType;

    private String title;
    private String description;
    private Integer deltaIntimacy;
    private Integer deltaTrust;
    private Integer deltaAffection;
    private Integer deltaConflict;
    private OffsetDateTime occurredAt;
    private String metadata;
}
