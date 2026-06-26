package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ConversationFeedback {
    private String id;
    private String userId;
    private String sessionId;
    private Integer score;
    private String comment;
    private OffsetDateTime createdAt;
}
