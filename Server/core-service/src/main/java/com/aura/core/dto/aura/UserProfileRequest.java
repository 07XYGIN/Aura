package com.aura.core.dto.aura;

import lombok.Data;

import java.time.LocalDate;

@Data
public class UserProfileRequest {
    private String displayName;
    private LocalDate birthday;
    private String pronouns;
    private String timezone;
    private String locale;
    private String preferences;
    private String boundaries;
    private String taboos;
    private String cityAdcode;
}
