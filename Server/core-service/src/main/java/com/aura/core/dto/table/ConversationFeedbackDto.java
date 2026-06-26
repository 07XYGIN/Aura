package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ConversationFeedbackDto {
    private String id;
    private String userId;
    private String sessionId;
    private Integer score;
    private String comment;
    private OffsetDateTime createdAt;
}
