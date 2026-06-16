package com.aura.core.dto.aura;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class MemoryItemRequest {
    private String auraProfileId;
    private String sourceSessionId;
    private String sourceMessageId;

    @NotBlank(message = "memoryType is required")
    private String memoryType;

    private String title;

    @NotBlank(message = "content is required")
    private String content;

    private Integer salience;
    private BigDecimal confidence;
    private String status;
    private String tags;
    private String metadata;
}
