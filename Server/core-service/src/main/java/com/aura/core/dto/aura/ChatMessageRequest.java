package com.aura.core.dto.aura;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatMessageRequest {
    @NotBlank(message = "senderType is required")
    private String senderType;

    private String senderId;

    @NotBlank(message = "content is required")
    private String content;

    private String contentType;
    private String emotionLabel;
    private Integer tokenCount;
    private String metadata;

    @Valid
    private EmotionSnapshotRequest emotionSnapshot;
}
