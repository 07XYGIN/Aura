package com.aura.core.dto.aura;

import com.aura.core.entity.ChatMessage;
import com.aura.core.entity.EmotionSnapshot;
import lombok.Data;

@Data
public class ChatMessageResponse {
    private ChatMessage message;
    private EmotionSnapshot emotionSnapshot;
}
