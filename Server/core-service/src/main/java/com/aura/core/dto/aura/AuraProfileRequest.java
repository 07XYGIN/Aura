package com.aura.core.dto.aura;

import lombok.Data;

@Data
public class AuraProfileRequest {
    private String id;
    private String nickname;
    private String personaSummary;
    private String voiceStyle;
    private String appearance;
    private String boundaries;
}
