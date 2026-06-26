package com.aura.core.entity;

import lombok.Data;

import java.time.LocalDate;
import java.time.OffsetDateTime;

@Data
public class DailyCheckin {
    private String id;
    private String userId;
    private LocalDate checkinDate;
    private OffsetDateTime morningSentAt;
    private OffsetDateTime eveningSentAt;
    private Integer interactionCount;
    private Integer streakDays;
    private String moodLabel;
    private String metadata;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
