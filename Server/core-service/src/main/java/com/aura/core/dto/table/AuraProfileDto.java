package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class AuraProfileDto {
    private String id;
    private String userId;
    private String nickname;
    private String personaSummary;
    private String voiceStyle;
    private String appearance;
    private String boundaries;
    private String systemPrompt;
    private String greetingStyle;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
