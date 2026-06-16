package com.aura.core.mapper;

import com.aura.core.entity.AuraProfile;
import com.aura.core.entity.ChatMessage;
import com.aura.core.entity.ConversationSession;
import com.aura.core.entity.EmotionSnapshot;
import com.aura.core.entity.MemoryItem;
import com.aura.core.entity.RelationshipEvent;
import com.aura.core.entity.RelationshipState;
import com.aura.core.entity.UserProfile;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

@Mapper
public interface AuraMapper {
    Integer acquireUserTransactionLock(@Param("userId") String userId);

    int upsertUserProfile(UserProfile userProfile);

    UserProfile findUserProfile(@Param("userId") String userId);

    int upsertAuraProfile(AuraProfile auraProfile);

    AuraProfile findAuraProfile(@Param("id") String id);

    AuraProfile findLatestAuraProfile(@Param("userId") String userId);

    int upsertRelationshipState(RelationshipState relationshipState);

    RelationshipState findRelationshipState(@Param("id") String id);

    RelationshipState findLatestRelationshipState(@Param("userId") String userId);

    int insertRelationshipEvent(RelationshipEvent relationshipEvent);

    List<RelationshipEvent> listRelationshipEvents(@Param("userId") String userId, @Param("limit") int limit);

    int insertConversationSession(ConversationSession session);

    int updateConversationSession(ConversationSession session);

    ConversationSession findConversationSession(@Param("id") String id);

    List<ConversationSession> listConversationSessions(@Param("userId") String userId, @Param("limit") int limit);

    int insertChatMessage(ChatMessage message);

    ChatMessage findChatMessage(@Param("id") String id);

    List<ChatMessage> listChatMessages(@Param("sessionId") String sessionId, @Param("limit") int limit);

    int deleteChatMessagesByUser(@Param("userId") String userId);

    int deleteEmptyConversationSessionsByUser(@Param("userId") String userId);

    int insertEmotionSnapshot(EmotionSnapshot snapshot);

    List<EmotionSnapshot> listEmotionSnapshotsBySession(@Param("sessionId") String sessionId, @Param("limit") int limit);

    int insertMemoryItem(MemoryItem memoryItem);

    List<MemoryItem> listMemoryItems(@Param("userId") String userId, @Param("limit") int limit);

    int deleteMemoryItemsByUser(@Param("userId") String userId);

    long countAdminAuraProfiles(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraProfiles(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);

    long countAdminAuraPersonas(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraPersonas(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);

    long countAdminAuraRelationships(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraRelationships(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);

    long countAdminAuraMessages(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraMessages(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);

    long countAdminAuraEmotions(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraEmotions(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);

    long countAdminAuraMemories(@Param("userId") String userId, @Param("keyword") String keyword);

    List<Map<String, Object>> listAdminAuraMemories(
            @Param("userId") String userId,
            @Param("keyword") String keyword,
            @Param("limit") int limit,
            @Param("offset") int offset);
}
