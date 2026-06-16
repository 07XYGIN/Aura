package com.aura.core.dto.aura;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class EmotionSnapshotRequest {
    private String sessionId;
    private String messageId;
    private String source;
    private String dominantEmotion;
    private BigDecimal valence;
    private BigDecimal arousal;
    private BigDecimal intensity;
    private String emotionScores;
    private String reason;
}
