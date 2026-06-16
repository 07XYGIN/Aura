package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ConversationSession {
    private String id;
    private String userId;
    private String auraProfileId;
    private String channel;
    private String title;
    private String status;
    private OffsetDateTime startedAt;
    private OffsetDateTime endedAt;
    private String summary;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
