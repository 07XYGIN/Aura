package com.aura.core.entity;

import lombok.Data;

import java.time.OffsetDateTime;

@Data
public class InvitationCodeRedemption {
    private String id;
    private String inviteCodeId;
    private String userId;
    private OffsetDateTime redeemedAt;
    private String metadata;
}
