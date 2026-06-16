package com.aura.core.dto.aura;

import com.aura.core.entity.AuraProfile;
import com.aura.core.entity.RelationshipState;
import com.aura.core.entity.UserProfile;
import lombok.Data;

@Data
public class InitialSetupResponse {
    private UserProfile userProfile;
    private AuraProfile auraProfile;
    private RelationshipState relationshipState;
}
