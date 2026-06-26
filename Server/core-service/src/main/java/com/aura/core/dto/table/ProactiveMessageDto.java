package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ProactiveMessageDto {
    private String id;
    private String userId;
    private String notificationPlanId;
    private String triggerType;
    private String title;
    private String content;
    private OffsetDateTime scheduledAt;
    private OffsetDateTime sentAt;
    private String status;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
