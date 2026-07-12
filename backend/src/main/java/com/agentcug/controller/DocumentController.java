package com.agentcug.controller;

import com.agentcug.model.dto.ApiResponse;
import com.agentcug.model.entity.Document;
import com.agentcug.model.entity.User;
import com.agentcug.service.DocumentService;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private final DocumentService documentService;

    public DocumentController(DocumentService documentService) {
        this.documentService = documentService;
    }

    @GetMapping("/kb/{kbId}")
    public ResponseEntity<ApiResponse<List<Document>>> list(
            @PathVariable Long kbId,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(documentService.listByKnowledgeBase(kbId, user.getId())));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @GetMapping("/kb/{kbId}/search")
    public ResponseEntity<ApiResponse<List<Document>>> search(
            @PathVariable Long kbId,
            @RequestParam String keyword,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(
                    documentService.searchByKeyword(kbId, keyword, user.getId())));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @PostMapping("/upload/{kbId}")
    public ResponseEntity<ApiResponse<Document>> upload(
            @PathVariable Long kbId,
            @RequestParam("file") MultipartFile file,
            @AuthenticationPrincipal User user) {
        try {
            Document doc = documentService.upload(file, kbId, user.getId());
            return ResponseEntity.ok(ApiResponse.success("上传成功", doc));
        } catch (RuntimeException | IOException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<Document>> get(
            @PathVariable Long id,
            @AuthenticationPrincipal User user) {
        try {
            return ResponseEntity.ok(ApiResponse.success(documentService.getById(id, user.getId())));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }

    @GetMapping("/{id}/download")
    public ResponseEntity<Resource> download(
            @PathVariable Long id,
            @AuthenticationPrincipal User user) {
        try {
            Document doc = documentService.getById(id, user.getId());
            Resource resource = new FileSystemResource(doc.getFilePath());
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "attachment; filename=\"" + doc.getOriginalName() + "\"")
                    .contentType(MediaType.APPLICATION_OCTET_STREAM)
                    .body(resource);
        } catch (RuntimeException e) {
            return ResponseEntity.notFound().build();
        }
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> delete(
            @PathVariable Long id,
            @AuthenticationPrincipal User user) {
        try {
            documentService.delete(id, user.getId());
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (RuntimeException | IOException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        }
    }
}