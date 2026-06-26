package com.aura.core.dto.table;

import lombok.Data;

import java.time.LocalTime;
import java.time.OffsetDateTime;

@Data
public class NotificationPlanDto {
    private String id;
    private String userId;
    private String planType;
    private String title;
    private String messageTemplate;
    private String timezone;
    private LocalTime morningWindowStart;
    private LocalTime morningWindowEnd;
    private LocalTime eveningWindowStart;
    private LocalTime eveningWindowEnd;
    private OffsetDateTime nextFireAt;
    private String randomSeed;
    private String status;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
