package com.aura.core.dto.aura;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class InitialSetupRequest {
    @NotBlank(message = "userId is required")
    private String userId;

    @Valid
    private UserProfileRequest userProfile;

    @Valid
    private AuraProfileRequest auraProfile;

    @Valid
    private RelationshipStateRequest relationshipState;
}
