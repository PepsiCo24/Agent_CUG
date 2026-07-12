package com.agentcug.controller;

import com.agentcug.model.dto.ApiResponse;
import com.agentcug.model.dto.KnowledgeBaseDTO;
import com.agentcug.model.entity.KnowledgeBase;
import com.agentcug.model.entity.User;
import com.agentcug.service.KnowledgeBaseService;
import javax.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.List;

@RestController
@RequestMapping("/api/knowledge-bases")
public class KnowledgeBaseController {

    private final KnowledgeBaseService kbService;

    public KnowledgeBaseController(KnowledgeBaseService kbService) {
        this.kbService = kbService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<KnowledgeBase>>> list(
            @AuthenticationPrincipal User user) {
        return ResponseEntity.ok(ApiResponse.success(kbService.listByUser(user.getId())));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<KnowledgeBase>> get(
            @PathVariable Long id,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(kbService.getById(id, user.getId())));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @PostMapping
    public ResponseEntity<ApiResponse<KnowledgeBase>> create(
            @Valid @RequestBody KnowledgeBaseDTO dto,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(kbService.create(dto, user)));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @PutMapping("/{id}")
    public ResponseEntity<ApiResponse<KnowledgeBase>> update(
            @PathVariable Long id,
            @Valid @RequestBody KnowledgeBaseDTO dto,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(kbService.update(id, dto, user.getId())));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> delete(
            @PathVariable Long id,
            @AuthenticationPrincipal User user) {
        try {
            kbService.delete(id, user.getId());
            return ResponseEntity.ok(ApiResponse.success("Deleted", null));
        } catch (RuntimeException | IOException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }
}