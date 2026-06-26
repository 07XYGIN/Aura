package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UserExportJob {
    private String id;
    private String userId;
    private String jobType;
    private String status;
    private String fileUrl;
    private OffsetDateTime requestedAt;
    private OffsetDateTime finishedAt;
    private String metadata;
}
