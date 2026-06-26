package com.aura.core.entity;

import lombok.Data;

import java.time.LocalDate;
import java.time.OffsetDateTime;

@Data
public class UserProfile {
    private String userId;
    private String displayName;
    private LocalDate birthday;
    private String pronouns;
    private String timezone;
    private String locale;
    private String preferences;
    private String boundaries;
    private String taboos;
    private String cityAdcode;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
