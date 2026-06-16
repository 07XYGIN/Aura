package com.aura.core.dto.aura;

import lombok.Data;

@Data
public class ConversationSessionRequest {
    private String auraProfileId;
    private String channel;
    private String title;
    private String status;
    private String summary;
    private String metadata;
}
