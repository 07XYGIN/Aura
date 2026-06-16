package com.aura.core.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

@Data
public class EmotionSnapshot {
    private String id;
    private String userId;
    private String sessionId;
    private String messageId;
    private String source;
    private String dominantEmotion;
    private BigDecimal valence;
    private BigDecimal arousal;
    private BigDecimal intensity;
    private String emotionScores;
    private String reason;
    private OffsetDateTime createdAt;
}
