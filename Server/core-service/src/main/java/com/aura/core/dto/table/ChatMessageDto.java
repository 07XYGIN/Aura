package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class ChatMessageDto {
    private String id;
    private String sessionId;
    private String userId;
    private String senderType;
    private String senderId;
    private String content;
    private String contentType;
    private String emotionLabel;
    private Integer tokenCount;
    private String metadata;
    private OffsetDateTime createdAt;
}
