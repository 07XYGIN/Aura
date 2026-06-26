package com.aura.core.dto.table;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class InvitationCodeRedemptionDto {
    private String id;
    private String inviteCodeId;
    private String userId;
    private OffsetDateTime redeemedAt;
    private String metadata;
}
