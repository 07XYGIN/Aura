package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class UserExportJobDto {
    private String id;
    private String userId;
    private String jobType;
    private String status;
    private String fileUrl;
    private OffsetDateTime requestedAt;
    private OffsetDateTime finishedAt;
    private String metadata;
}
