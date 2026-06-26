package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ProactiveMessage {
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
