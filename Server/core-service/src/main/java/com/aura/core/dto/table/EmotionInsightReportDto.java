package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class EmotionInsightReportDto {
    private String id;
    private String userId;
    private String status;
    private Integer priceCents;
    private String previewKeywords;
    private String previewText;
    private String fullReport;
    private OffsetDateTime paidAt;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
