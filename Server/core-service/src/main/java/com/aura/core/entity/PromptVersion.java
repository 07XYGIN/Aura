package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class PromptVersion {
    private String id;
    private String name;
    private String version;
    private String promptType;
    private String content;
    private String status;
    private String createdBy;
    private OffsetDateTime createdAt;
}
