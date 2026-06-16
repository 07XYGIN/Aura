package com.aura.core.controller;

import com.aura.core.common.Response;
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
import com.aura.core.entity.ChatMessage;
import com.aura.core.entity.ConversationSession;
import com.aura.core.entity.EmotionSnapshot;
import com.aura.core.entity.MemoryItem;
import com.aura.core.entity.RelationshipEvent;
import com.aura.core.entity.RelationshipState;
import com.aura.core.service.AuraService;
import com.aura.core.util.JWTUtil;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/aura")
public class AuraController {
    private final AuraService auraService;
    private final JWTUtil jwtUtil;

    public AuraController(AuraService auraService, JWTUtil jwtUtil) {
        this.auraService = auraService;
        this.jwtUtil = jwtUtil;
    }

    @GetMapping("initial-setting")
    public Response<InitialSetupResponse> getInitialSetting(@RequestHeader("Authorization") String authHeader) {
        return Response.success(auraService.getInitialSetup(getCurrentUserId(authHeader)));
    }

    @PostMapping("initial-setting")
    public Response<InitialSetupResponse> saveInitialSetting(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody InitialSetupRequest request) {
        request.setUserId(getCurrentUserId(authHeader));
        return Response.success(auraService.saveInitialSetup(request));
    }

    @GetMapping("relationship/status")
    public Response<RelationshipState> getRelationshipStatus(@RequestHeader("Authorization") String authHeader) {
        return Response.success(auraService.getRelationshipState(getCurrentUserId(authHeader)));
    }

    @PutMapping("relationship/status")
    public Response<RelationshipState> updateRelationshipStatus(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody RelationshipStateRequest request) {
        RelationshipState response = auraService.updateRelationshipState(getCurrentUserId(authHeader), request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @PostMapping("relationship/events")
    public Response<RelationshipEvent> addRelationshipEvent(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody RelationshipEventRequest request) {
        RelationshipEvent response = auraService.addRelationshipEvent(getCurrentUserId(authHeader), request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @GetMapping("relationship/events")
    public Response<List<RelationshipEvent>> listRelationshipEvents(
            @RequestHeader("Authorization") String authHeader,
            @RequestParam(required = false) Integer limit) {
        return Response.success(auraService.listRelationshipEvents(getCurrentUserId(authHeader), limit));
    }

    @PostMapping("sessions")
    public Response<ConversationSession> createSession(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody ConversationSessionRequest request) {
        ConversationSession response = auraService.createSession(getCurrentUserId(authHeader), request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @GetMapping("sessions")
    public Response<List<ConversationSession>> listSessions(
            @RequestHeader("Authorization") String authHeader,
            @RequestParam(required = false) Integer limit) {
        return Response.success(auraService.listSessions(getCurrentUserId(authHeader), limit));
    }

    @GetMapping("sessions/current/messages")
    public Response<List<ChatMessage>> listCurrentSessionMessages(
            @RequestHeader("Authorization") String authHeader,
            @RequestParam(required = false) Integer limit) {
        return Response.success(auraService.listCurrentSessionMessages(getCurrentUserId(authHeader), limit));
    }

    @DeleteMapping("sessions/current/messages")
    public Response<Map<String, Integer>> clearCurrentSessionMessages(@RequestHeader("Authorization") String authHeader) {
        int deletedCount = auraService.clearCurrentSessionMessages(getCurrentUserId(authHeader));
        return Response.success(Map.of("deletedCount", deletedCount));
    }

    @PutMapping("sessions/{sessionId}")
    public Response<ConversationSession> updateSession(
            @RequestHeader("Authorization") String authHeader,
            @PathVariable String sessionId,
            @Valid @RequestBody ConversationSessionRequest request) {
        ConversationSession response = auraService.updateSession(getCurrentUserId(authHeader), sessionId, request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @PostMapping("sessions/{sessionId}/messages")
    public Response<ChatMessageResponse> addMessage(
            @RequestHeader("Authorization") String authHeader,
            @PathVariable String sessionId,
            @Valid @RequestBody ChatMessageRequest request) {
        ChatMessageResponse response = auraService.addMessage(getCurrentUserId(authHeader), sessionId, request);
        if (response == null) {
            return Response.error(404, "会话不存在或无权访问");
        }
        return Response.success(response);
    }

    @GetMapping("sessions/{sessionId}/messages")
    public Response<List<ChatMessage>> listMessages(
            @RequestHeader("Authorization") String authHeader,
            @PathVariable String sessionId,
            @RequestParam(required = false) Integer limit) {
        List<ChatMessage> response = auraService.listMessages(getCurrentUserId(authHeader), sessionId, limit);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @PostMapping("emotion-snapshots")
    public Response<EmotionSnapshot> addEmotionSnapshot(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody EmotionSnapshotRequest request) {
        EmotionSnapshot response = auraService.addEmotionSnapshot(getCurrentUserId(authHeader), request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @GetMapping("sessions/{sessionId}/emotion-snapshots")
    public Response<List<EmotionSnapshot>> listEmotionSnapshots(
            @RequestHeader("Authorization") String authHeader,
            @PathVariable String sessionId,
            @RequestParam(required = false) Integer limit) {
        List<EmotionSnapshot> response = auraService.listEmotionSnapshots(getCurrentUserId(authHeader), sessionId, limit);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @PostMapping("memories")
    public Response<MemoryItem> addMemoryItem(
            @RequestHeader("Authorization") String authHeader,
            @Valid @RequestBody MemoryItemRequest request) {
        MemoryItem response = auraService.addMemoryItem(getCurrentUserId(authHeader), request);
        if (response == null) {
            return Response.error(404, "resource not found or forbidden");
        }
        return Response.success(response);
    }

    @GetMapping("memories")
    public Response<List<MemoryItem>> listMemoryItems(
            @RequestHeader("Authorization") String authHeader,
            @RequestParam(required = false) Integer limit) {
        return Response.success(auraService.listMemoryItems(getCurrentUserId(authHeader), limit));
    }

    @DeleteMapping("memories")
    public Response<Map<String, Integer>> clearMemoryItems(@RequestHeader("Authorization") String authHeader) {
        int deletedCount = auraService.clearMemoryItems(getCurrentUserId(authHeader));
        return Response.success(Map.of("deletedCount", deletedCount));
    }

    @GetMapping("admin/profiles")
    public Response<AdminAuraPageResponse> listAdminAuraProfiles(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraProfiles(userId, keyword, page, pageSize));
    }

    @GetMapping("admin/personas")
    public Response<AdminAuraPageResponse> listAdminAuraPersonas(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraPersonas(userId, keyword, page, pageSize));
    }

    @GetMapping("admin/relationships")
    public Response<AdminAuraPageResponse> listAdminAuraRelationships(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraRelationships(userId, keyword, page, pageSize));
    }

    @GetMapping("admin/messages")
    public Response<AdminAuraPageResponse> listAdminAuraMessages(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraMessages(userId, keyword, page, pageSize));
    }

    @GetMapping("admin/emotions")
    public Response<AdminAuraPageResponse> listAdminAuraEmotions(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraEmotions(userId, keyword, page, pageSize));
    }

    @GetMapping("admin/memories")
    public Response<AdminAuraPageResponse> listAdminAuraMemories(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return Response.success(auraService.listAdminAuraMemories(userId, keyword, page, pageSize));
    }

    private String getCurrentUserId(String authHeader) {
        return jwtUtil.getUsernameFromToken(authHeader.replace("Bearer ", ""));
    }
}
