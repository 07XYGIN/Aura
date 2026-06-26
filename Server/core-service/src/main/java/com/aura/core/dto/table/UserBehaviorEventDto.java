package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UserBehaviorEventDto {
    private String id;
    private String userId;
    private String sessionId;
    private String messageId;
    private String eventType;
    private OffsetDateTime eventTime;
    private String metadata;
    private OffsetDateTime createdAt;
}
