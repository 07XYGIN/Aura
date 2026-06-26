package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class PromptVersionDto {
    private String id;
    private String name;
    private String version;
    private String promptType;
    private String content;
    private String status;
    private String createdBy;
    private OffsetDateTime createdAt;
}
