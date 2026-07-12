package com.agentcug.controller;

import com.agentcug.model.dto.ApiResponse;
import com.agentcug.model.dto.ChatRequest;
import com.agentcug.model.dto.ChatResponse;
import com.agentcug.model.entity.ChatMessage;
import com.agentcug.model.entity.User;
import com.agentcug.gateway.anythingllm.RagGatewayClient;
import com.agentcug.service.ChatService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import javax.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService chatService;
    private final RagGatewayClient ragGatewayClient;
    private final ObjectMapper objectMapper;

    public ChatController(ChatService chatService,
                          RagGatewayClient ragGatewayClient,
                          ObjectMapper objectMapper) {
        this.chatService = chatService;
        this.ragGatewayClient = ragGatewayClient;
        this.objectMapper = objectMapper;
    }

    @PostMapping("/{kbId}")
    public ResponseEntity<ApiResponse<ChatResponse>> chat(
            @PathVariable Long kbId,
            @Valid @RequestBody ChatRequest request,
            @AuthenticationPrincipal User user) {
        try {
            List<ChatMessage> history = chatService.getConversationHistory(kbId, user.getId());
            List<Map<String, String>> historyMap = history.stream()
                    .map(msg -> {
                        Map<String, String> m = new HashMap<>();
                        m.put("role", msg.getRole().toLowerCase());
                        m.put("content", msg.getContent());
                        return m;
                    })
                    .collect(Collectors.toList());

            chatService.saveMessage(kbId, user.getId(), "USER", request.getQuestion(), null);

            ChatResponse response = ragGatewayClient.chat(
                    String.valueOf(kbId), request.getQuestion(), historyMap).block();

            String citationsJson = "[]";
            if (response != null && response.getCitations() != null) {
                try {
                    citationsJson = objectMapper.writeValueAsString(response.getCitations());
                } catch (JsonProcessingException ignored) {}
            }

            if (response != null) {
                chatService.saveMessage(kbId, user.getId(), "ASSISTANT", response.getAnswer(), citationsJson);
            }

            return ResponseEntity.ok(ApiResponse.success(response));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @GetMapping("/{kbId}/history")
    public ResponseEntity<ApiResponse<List<ChatMessage>>> history(
            @PathVariable Long kbId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size,
            @AuthenticationPrincipal User user) {
        try {
            Page<ChatMessage> pageResult = chatService.getHistory(kbId, user.getId(), page, size);
            return ResponseEntity.ok(ApiResponse.success(pageResult.getContent()));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @DeleteMapping("/{kbId}/history")
    public ResponseEntity<ApiResponse<Void>> clearHistory(
            @PathVariable Long kbId,
            @AuthenticationPrincipal User user) {
        try {
            chatService.clearHistory(kbId, user.getId());
            return ResponseEntity.ok(ApiResponse.success("cleared", null));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }
}