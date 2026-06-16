package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class AuraProfile {
    private String id;
    private String userId;
    private String nickname;
    private String personaSummary;
    private String voiceStyle;
    private String appearance;
    private String boundaries;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
