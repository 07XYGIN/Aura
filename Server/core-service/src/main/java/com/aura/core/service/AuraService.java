package com.aura.core.service;

import com.aura.core.dto.aura.AuraProfileRequest;
import com.aura.core.dto.aura.AdminAuraPageResponse;
import com.aura.core.dto.aura.ChatMessageRequest;
import com.aura.core.dto.aura.ChatMessageResponse;
import com.aura.core.dto.aura.ConversationSessionRequest;
import com.aura.core.dto.aura.EmotionSnapshotRequest;
import com.aura.core.dto.aura.InitialSetupRequest;
import com.aura.core.dto.aura.InitialSetupResponse;
import com.aura.core.dto.aura.MemoryItemRequest;
import com.aura.core.dto.aura.RelationshipEventRequest;
import com.aura.core.dto.aura.RelationshipStateRequest;
import com.aura.core.dto.aura.UserProfileRequest;
import com.aura.core.entity.AuraProfile;
import com.aura.core.entity.ChatMessage;
import com.aura.core.entity.ConversationSession;
import com.aura.core.entity.EmotionSnapshot;
import com.aura.core.entity.MemoryItem;
import com.aura.core.entity.RelationshipEvent;
import com.aura.core.entity.RelationshipState;
import com.aura.core.entity.UserProfile;
import com.aura.core.mapper.AuraMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AuraService {
    private static final Logger log = LoggerFactory.getLogger(AuraService.class);
    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT = 200;
    private static final String DEFAULT_TIMEZONE = "Asia/Shanghai";
    private static final String DEFAULT_LOCALE = "zh-CN";

    private final AuraMapper auraMapper;

    public AuraService(AuraMapper auraMapper) {
        this.auraMapper = auraMapper;
    }

    @Transactional
    public InitialSetupResponse saveInitialSetup(InitialSetupRequest request) {
        log.info("Saving initial setup userId={}", request.getUserId());
        lockUser(request.getUserId());
        UserProfile userProfile = toUserProfile(request.getUserId(), request.getUserProfile());
        auraMapper.upsertUserProfile(userProfile);

        AuraProfile auraProfile = toAuraProfile(request.getUserId(), request.getAuraProfile());
        AuraProfile existingAuraProfile = auraMapper.findLatestAuraProfile(request.getUserId());
        if (existingAuraProfile != null) {
            auraProfile.setId(existingAuraProfile.getId());
        }
        auraMapper.upsertAuraProfile(auraProfile);
        auraProfile = auraMapper.findLatestAuraProfile(request.getUserId());

        RelationshipState relationshipState = toRelationshipState(
                request.getUserId(),
                auraProfile.getId(),
                request.getRelationshipState()
        );
        RelationshipState existingState = auraMapper.findLatestRelationshipState(request.getUserId());
        if (existingState != null) {
            relationshipState.setId(existingState.getId());
        }
        auraMapper.upsertRelationshipState(relationshipState);

        InitialSetupResponse response = new InitialSetupResponse();
        response.setUserProfile(auraMapper.findUserProfile(request.getUserId()));
        response.setAuraProfile(auraMapper.findLatestAuraProfile(request.getUserId()));
        response.setRelationshipState(auraMapper.findLatestRelationshipState(request.getUserId()));
        return response;
    }

    public InitialSetupResponse getInitialSetup(String userId) {
        log.info("Loading initial setup userId={}", userId);
        InitialSetupResponse response = new InitialSetupResponse();
        response.setUserProfile(auraMapper.findUserProfile(userId));
        response.setAuraProfile(auraMapper.findLatestAuraProfile(userId));
        response.setRelationshipState(auraMapper.findLatestRelationshipState(userId));
        return response;
    }

    public RelationshipState getRelationshipState(String userId) {
        log.info("Loading relationship state userId={}", userId);
        return auraMapper.findLatestRelationshipState(userId);
    }

    @Transactional
    public RelationshipState updateRelationshipState(String userId, RelationshipStateRequest request) {
        log.info("Updating relationship state userId={}", userId);
        lockUser(userId);
        AuraProfile auraProfile = auraMapper.findLatestAuraProfile(userId);
        String auraProfileId = firstNonBlank(request.getAuraProfileId(), auraProfile == null ? null : auraProfile.getId());
        if (!isBlank(auraProfileId) && !isOwnedAuraProfile(userId, auraProfileId)) {
            return null;
        }
        RelationshipState currentState = auraMapper.findLatestRelationshipState(userId);
        RelationshipState nextState = toRelationshipState(userId, auraProfileId, request);
        if (currentState != null) {
            nextState.setId(currentState.getId());
            nextState.setAuraProfileId(firstNonBlank(nextState.getAuraProfileId(), currentState.getAuraProfileId()));
            nextState.setRelationshipStage(firstNonBlank(nextState.getRelationshipStage(), currentState.getRelationshipStage()));
            nextState.setIntimacyLevel(firstNonNull(nextState.getIntimacyLevel(), currentState.getIntimacyLevel()));
            nextState.setTrustLevel(firstNonNull(nextState.getTrustLevel(), currentState.getTrustLevel()));
            nextState.setAffectionLevel(firstNonNull(nextState.getAffectionLevel(), currentState.getAffectionLevel()));
            nextState.setConflictLevel(firstNonNull(nextState.getConflictLevel(), currentState.getConflictLevel()));
            nextState.setCurrentMood(firstNonBlank(nextState.getCurrentMood(), currentState.getCurrentMood()));
            nextState.setLastInteractionAt(firstNonNull(nextState.getLastInteractionAt(), currentState.getLastInteractionAt()));
            nextState.setMetadata(firstNonNull(nextState.getMetadata(), currentState.getMetadata()));
        }
        auraMapper.upsertRelationshipState(nextState);
        return auraMapper.findLatestRelationshipState(userId);
    }

    @Transactional
    public RelationshipEvent addRelationshipEvent(String userId, RelationshipEventRequest request) {
        log.info("Adding relationship event userId={} eventType={}", userId, request.getEventType());
        lockUser(userId);
        RelationshipEvent event = new RelationshipEvent();
        event.setId(newId());
        event.setUserId(userId);
        event.setRelationshipStateId(nullIfBlank(request.getRelationshipStateId()));
        if (isBlank(event.getRelationshipStateId())) {
            RelationshipState state = auraMapper.findLatestRelationshipState(userId);
            event.setRelationshipStateId(state == null ? null : state.getId());
        } else if (!isOwnedRelationshipState(userId, event.getRelationshipStateId())) {
            return null;
        }
        event.setEventType(request.getEventType());
        event.setTitle(request.getTitle());
        event.setDescription(request.getDescription());
        event.setDeltaIntimacy(defaultNumber(request.getDeltaIntimacy()));
        event.setDeltaTrust(defaultNumber(request.getDeltaTrust()));
        event.setDeltaAffection(defaultNumber(request.getDeltaAffection()));
        event.setDeltaConflict(defaultNumber(request.getDeltaConflict()));
        event.setOccurredAt(firstNonNull(request.getOccurredAt(), OffsetDateTime.now()));
        event.setMetadata(request.getMetadata());
        auraMapper.insertRelationshipEvent(event);
        return event;
    }

    public List<RelationshipEvent> listRelationshipEvents(String userId, Integer limit) {
        return auraMapper.listRelationshipEvents(userId, normalizeLimit(limit));
    }

    @Transactional
    public ConversationSession createSession(String userId, ConversationSessionRequest request) {
        log.info("Creating conversation session userId={} channel={}", userId, request.getChannel());
        lockUser(userId);
        ConversationSession session = new ConversationSession();
        session.setId(newId());
        session.setUserId(userId);
        session.setAuraProfileId(nullIfBlank(request.getAuraProfileId()));
        if (isBlank(session.getAuraProfileId())) {
            AuraProfile auraProfile = auraMapper.findLatestAuraProfile(userId);
            session.setAuraProfileId(auraProfile == null ? null : auraProfile.getId());
        } else if (!isOwnedAuraProfile(userId, session.getAuraProfileId())) {
            return null;
        }
        session.setChannel(firstNonBlank(request.getChannel(), "chat"));
        session.setTitle(request.getTitle());
        session.setStatus(firstNonBlank(request.getStatus(), "active"));
        session.setStartedAt(OffsetDateTime.now());
        session.setSummary(request.getSummary());
        session.setMetadata(request.getMetadata());
        auraMapper.insertConversationSession(session);
        return auraMapper.findConversationSession(session.getId());
    }

    public ConversationSession getSession(String sessionId) {
        return auraMapper.findConversationSession(sessionId);
    }

    public List<ConversationSession> listSessions(String userId, Integer limit) {
        return auraMapper.listConversationSessions(userId, normalizeLimit(limit));
    }

    public List<ChatMessage> listCurrentSessionMessages(String userId, Integer limit) {
        log.info("Listing current session messages userId={} limit={}", userId, limit);
        List<ConversationSession> sessions = auraMapper.listConversationSessions(userId, 1);
        if (sessions.isEmpty()) {
            return List.of();
        }
        return auraMapper.listChatMessages(sessions.get(0).getId(), normalizeLimit(limit));
    }

    @Transactional
    public int clearCurrentSessionMessages(String userId) {
        log.info("Clearing auxiliary chat history userId={}", userId);
        lockUser(userId);
        int deletedMessages = auraMapper.deleteChatMessagesByUser(userId);
        auraMapper.deleteEmptyConversationSessionsByUser(userId);
        return deletedMessages;
    }

    @Transactional
    public ConversationSession updateSession(String userId, String sessionId, ConversationSessionRequest request) {
        lockUser(userId);
        ConversationSession currentSession = auraMapper.findConversationSession(sessionId);
        if (currentSession == null || !userId.equals(currentSession.getUserId())) {
            return null;
        }
        String auraProfileId = nullIfBlank(request.getAuraProfileId());
        if (auraProfileId != null && !isOwnedAuraProfile(userId, auraProfileId)) {
            return null;
        }

        ConversationSession session = new ConversationSession();
        session.setId(sessionId);
        session.setAuraProfileId(auraProfileId);
        session.setChannel(request.getChannel());
        session.setTitle(request.getTitle());
        session.setStatus(request.getStatus());
        if ("ended".equals(request.getStatus()) || "closed".equals(request.getStatus())) {
            session.setEndedAt(OffsetDateTime.now());
        }
        session.setSummary(request.getSummary());
        session.setMetadata(request.getMetadata());
        auraMapper.updateConversationSession(session);
        return auraMapper.findConversationSession(sessionId);
    }

    @Transactional
    public ChatMessageResponse addMessage(String userId, String sessionId, ChatMessageRequest request) {
        log.info("Adding chat message userId={} sessionId={} senderType={}", userId, sessionId, request.getSenderType());
        lockUser(userId);
        ConversationSession session = auraMapper.findConversationSession(sessionId);
        if (session == null || !userId.equals(session.getUserId())) {
            return null;
        }

        ChatMessage message = new ChatMessage();
        message.setId(newId());
        message.setSessionId(sessionId);
        message.setUserId(userId);
        message.setSenderType(request.getSenderType());
        message.setSenderId(request.getSenderId());
        message.setContent(request.getContent());
        message.setContentType(firstNonBlank(request.getContentType(), "text"));
        message.setEmotionLabel(request.getEmotionLabel());
        message.setTokenCount(defaultNumber(request.getTokenCount()));
        message.setMetadata(request.getMetadata());
        auraMapper.insertChatMessage(message);

        EmotionSnapshot snapshot = null;
        if (request.getEmotionSnapshot() != null) {
            snapshot = toEmotionSnapshot(userId, sessionId, message.getId(), request.getEmotionSnapshot());
            auraMapper.insertEmotionSnapshot(snapshot);
        }

        ChatMessageResponse response = new ChatMessageResponse();
        response.setMessage(auraMapper.findChatMessage(message.getId()));
        response.setEmotionSnapshot(snapshot);
        return response;
    }

    public List<ChatMessage> listMessages(String userId, String sessionId, Integer limit) {
        if (!isOwnedSession(userId, sessionId)) {
            return null;
        }
        return auraMapper.listChatMessages(sessionId, normalizeLimit(limit));
    }

    @Transactional
    public EmotionSnapshot addEmotionSnapshot(String userId, EmotionSnapshotRequest request) {
        log.info("Adding emotion snapshot userId={} sessionId={} messageId={}", userId, request.getSessionId(), request.getMessageId());
        lockUser(userId);
        EmotionSnapshot snapshot = toEmotionSnapshot(userId, request.getSessionId(), request.getMessageId(), request);
        if (!isBlank(snapshot.getSessionId()) && !isOwnedSession(userId, snapshot.getSessionId())) {
            return null;
        }
        if (!isBlank(snapshot.getMessageId()) && !isOwnedMessage(userId, snapshot.getMessageId())) {
            return null;
        }
        auraMapper.insertEmotionSnapshot(snapshot);
        return snapshot;
    }

    public List<EmotionSnapshot> listEmotionSnapshots(String userId, String sessionId, Integer limit) {
        if (!isOwnedSession(userId, sessionId)) {
            return null;
        }
        return auraMapper.listEmotionSnapshotsBySession(sessionId, normalizeLimit(limit));
    }

    @Transactional
    public MemoryItem addMemoryItem(String userId, MemoryItemRequest request) {
        log.info("Adding memory item userId={} memoryType={} title={}", userId, request.getMemoryType(), request.getTitle());
        lockUser(userId);
        MemoryItem memoryItem = new MemoryItem();
        memoryItem.setId(newId());
        memoryItem.setUserId(userId);
        memoryItem.setAuraProfileId(nullIfBlank(request.getAuraProfileId()));
        memoryItem.setSourceSessionId(nullIfBlank(request.getSourceSessionId()));
        memoryItem.setSourceMessageId(nullIfBlank(request.getSourceMessageId()));
        if (!isBlank(memoryItem.getAuraProfileId()) && !isOwnedAuraProfile(userId, memoryItem.getAuraProfileId())) {
            return null;
        }
        if (!isBlank(memoryItem.getSourceSessionId()) && !isOwnedSession(userId, memoryItem.getSourceSessionId())) {
            return null;
        }
        if (!isBlank(memoryItem.getSourceMessageId()) && !isOwnedMessage(userId, memoryItem.getSourceMessageId())) {
            return null;
        }
        memoryItem.setMemoryType(request.getMemoryType());
        memoryItem.setTitle(request.getTitle());
        memoryItem.setContent(request.getContent());
        memoryItem.setSalience(firstNonNull(request.getSalience(), 50));
        memoryItem.setConfidence(request.getConfidence());
        memoryItem.setStatus(firstNonBlank(request.getStatus(), "active"));
        memoryItem.setTags(request.getTags());
        memoryItem.setMetadata(request.getMetadata());
        auraMapper.insertMemoryItem(memoryItem);
        return memoryItem;
    }

    public List<MemoryItem> listMemoryItems(String userId, Integer limit) {
        return auraMapper.listMemoryItems(userId, normalizeLimit(limit));
    }

    @Transactional
    public int clearMemoryItems(String userId) {
        log.info("Clearing auxiliary memory items userId={}", userId);
        lockUser(userId);
        return auraMapper.deleteMemoryItemsByUser(userId);
    }

    public AdminAuraPageResponse listAdminAuraProfiles(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura profiles userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraProfiles(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraProfiles(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    public AdminAuraPageResponse listAdminAuraPersonas(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura personas userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraPersonas(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraPersonas(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    public AdminAuraPageResponse listAdminAuraRelationships(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura relationships userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraRelationships(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraRelationships(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    public AdminAuraPageResponse listAdminAuraMessages(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura messages userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraMessages(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraMessages(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    public AdminAuraPageResponse listAdminAuraEmotions(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura emotions userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraEmotions(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraEmotions(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    public AdminAuraPageResponse listAdminAuraMemories(String userId, String keyword, Integer page, Integer pageSize) {
        log.info("Listing admin Aura memories userId={} keyword={} page={} pageSize={}", userId, keyword, page, pageSize);
        return buildAdminPage(
                auraMapper.countAdminAuraMemories(userId, normalizeKeyword(keyword)),
                auraMapper.listAdminAuraMemories(userId, normalizeKeyword(keyword), normalizeLimit(pageSize), offset(page, pageSize)),
                page,
                pageSize
        );
    }

    private UserProfile toUserProfile(String userId, UserProfileRequest request) {
        UserProfile profile = new UserProfile();
        profile.setUserId(userId);
        if (request != null) {
            profile.setDisplayName(request.getDisplayName());
            profile.setBirthday(request.getBirthday());
            profile.setPronouns(request.getPronouns());
            profile.setTimezone(firstNonBlank(request.getTimezone(), DEFAULT_TIMEZONE));
            profile.setLocale(firstNonBlank(request.getLocale(), DEFAULT_LOCALE));
            profile.setPreferences(request.getPreferences());
        } else {
            profile.setTimezone(DEFAULT_TIMEZONE);
            profile.setLocale(DEFAULT_LOCALE);
        }
        return profile;
    }

    private AuraProfile toAuraProfile(String userId, AuraProfileRequest request) {
        AuraProfile auraProfile = new AuraProfile();
        auraProfile.setId(request != null && !isBlank(request.getId()) ? request.getId() : newId());
        auraProfile.setUserId(userId);
        if (request != null) {
            auraProfile.setNickname(firstNonBlank(request.getNickname(), "Aura"));
            auraProfile.setPersonaSummary(request.getPersonaSummary());
            auraProfile.setVoiceStyle(request.getVoiceStyle());
            auraProfile.setAppearance(request.getAppearance());
            auraProfile.setBoundaries(request.getBoundaries());
        } else {
            auraProfile.setNickname("Aura");
        }
        return auraProfile;
    }

    private RelationshipState toRelationshipState(String userId, String auraProfileId, RelationshipStateRequest request) {
        RelationshipState state = new RelationshipState();
        state.setId(request != null && !isBlank(request.getId()) ? request.getId() : newId());
        state.setUserId(userId);
        state.setAuraProfileId(nullIfBlank(request == null ? auraProfileId : firstNonBlank(request.getAuraProfileId(), auraProfileId)));
        state.setRelationshipStage(request == null ? "new" : firstNonBlank(request.getRelationshipStage(), "new"));
        state.setIntimacyLevel(request == null ? 0 : firstNonNull(request.getIntimacyLevel(), 0));
        state.setTrustLevel(request == null ? 0 : firstNonNull(request.getTrustLevel(), 0));
        state.setAffectionLevel(request == null ? 0 : firstNonNull(request.getAffectionLevel(), 0));
        state.setConflictLevel(request == null ? 0 : firstNonNull(request.getConflictLevel(), 0));
        state.setCurrentMood(request == null ? "neutral" : firstNonBlank(request.getCurrentMood(), "neutral"));
        state.setLastInteractionAt(request == null ? OffsetDateTime.now() : firstNonNull(request.getLastInteractionAt(), OffsetDateTime.now()));
        state.setMetadata(request == null ? null : request.getMetadata());
        return state;
    }

    private EmotionSnapshot toEmotionSnapshot(String userId, String sessionId, String messageId, EmotionSnapshotRequest request) {
        EmotionSnapshot snapshot = new EmotionSnapshot();
        snapshot.setId(newId());
        snapshot.setUserId(userId);
        snapshot.setSessionId(nullIfBlank(firstNonBlank(request.getSessionId(), sessionId)));
        snapshot.setMessageId(nullIfBlank(firstNonBlank(request.getMessageId(), messageId)));
        snapshot.setSource(firstNonBlank(request.getSource(), "chat"));
        snapshot.setDominantEmotion(request.getDominantEmotion());
        snapshot.setValence(request.getValence());
        snapshot.setArousal(request.getArousal());
        snapshot.setIntensity(request.getIntensity());
        snapshot.setEmotionScores(request.getEmotionScores());
        snapshot.setReason(request.getReason());
        return snapshot;
    }

    private int normalizeLimit(Integer limit) {
        if (limit == null || limit <= 0) {
            return DEFAULT_LIMIT;
        }
        return Math.min(limit, MAX_LIMIT);
    }

    private int offset(Integer page, Integer pageSize) {
        int currentPage = page == null || page <= 0 ? 1 : page;
        int currentPageSize = normalizeLimit(pageSize);
        return (currentPage - 1) * currentPageSize;
    }

    private String normalizeKeyword(String keyword) {
        return isBlank(keyword) ? null : keyword.trim();
    }

    private AdminAuraPageResponse buildAdminPage(long total, List<Map<String, Object>> items, Integer page, Integer pageSize) {
        AdminAuraPageResponse response = new AdminAuraPageResponse();
        response.setItems(items);
        response.setTotal(total);
        response.setPage(page == null || page <= 0 ? 1 : page);
        response.setPageSize(normalizeLimit(pageSize));
        return response;
    }

    private int defaultNumber(Integer value) {
        return value == null ? 0 : value;
    }

    private String newId() {
        return UUID.randomUUID().toString();
    }

    private void lockUser(String userId) {
        auraMapper.acquireUserTransactionLock(userId);
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private String firstNonBlank(String value, String defaultValue) {
        return isBlank(value) ? defaultValue : value;
    }

    private String nullIfBlank(String value) {
        return isBlank(value) ? null : value;
    }

    private boolean isOwnedAuraProfile(String userId, String auraProfileId) {
        AuraProfile auraProfile = auraMapper.findAuraProfile(auraProfileId);
        return auraProfile != null && userId.equals(auraProfile.getUserId());
    }

    private boolean isOwnedRelationshipState(String userId, String relationshipStateId) {
        RelationshipState relationshipState = auraMapper.findRelationshipState(relationshipStateId);
        return relationshipState != null && userId.equals(relationshipState.getUserId());
    }

    private boolean isOwnedSession(String userId, String sessionId) {
        ConversationSession session = auraMapper.findConversationSession(sessionId);
        return session != null && userId.equals(session.getUserId());
    }

    private boolean isOwnedMessage(String userId, String messageId) {
        ChatMessage message = auraMapper.findChatMessage(messageId);
        return message != null && userId.equals(message.getUserId());
    }

    private <T> T firstNonNull(T value, T defaultValue) {
        return value == null ? defaultValue : value;
    }
}
