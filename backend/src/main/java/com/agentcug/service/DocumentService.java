package com.agentcug.service;

import com.agentcug.model.entity.Document;
import com.agentcug.model.entity.KnowledgeBase;
import com.agentcug.repository.DocumentRepository;
import com.agentcug.repository.KnowledgeBaseRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.UUID;

@Service
public class DocumentService {

    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);

    private final DocumentRepository documentRepository;
    private final KnowledgeBaseRepository kbRepository;
    private final KnowledgeBaseService kbService;
    private final DocumentProcessingService processingService;
    private final Path uploadDir;

    public DocumentService(DocumentRepository documentRepository,
                           KnowledgeBaseRepository kbRepository,
                           KnowledgeBaseService kbService,
                           DocumentProcessingService processingService,
                           @Value("${app.upload-dir}") String uploadDir) {
        this.documentRepository = documentRepository;
        this.kbRepository = kbRepository;
        this.kbService = kbService;
        this.processingService = processingService;
        this.uploadDir = Paths.get(uploadDir).toAbsolutePath().normalize();
        try {
            Files.createDirectories(this.uploadDir);
        } catch (IOException e) {
            throw new RuntimeException("Cannot create upload directory", e);
        }
    }

    public List<Document> listByKnowledgeBase(Long kbId, Long userId) {
        kbService.getById(kbId, userId);
        return documentRepository.findByKnowledgeBaseId(kbId);
    }

    public List<Document> searchByKeyword(Long kbId, String keyword, Long userId) {
        kbService.getById(kbId, userId);
        return documentRepository.findByKnowledgeBaseIdAndFileNameContainingIgnoreCase(kbId, keyword);
    }

    @Transactional
    public Document upload(MultipartFile file, Long kbId, Long userId) throws IOException {
        KnowledgeBase kb = kbService.getById(kbId, userId);

        String originalName = file.getOriginalFilename();
        String extension = getFileExtension(originalName);
        String storedName = UUID.randomUUID().toString() + extension;

        Path targetPath = uploadDir.resolve(storedName);
        file.transferTo(targetPath.toFile());

        Document doc = Document.builder()
                .fileName(storedName)
                .originalName(originalName)
                .filePath(targetPath.toString())
                .fileSize(file.getSize())
                .fileType(getFileType(extension))
                .mimeType(file.getContentType())
                .knowledgeBase(kb)
                .user(kb.getUser())
                .parseStatus("PENDING")
                .embeddingStatus("PENDING")
                .build();

        final Document saved = documentRepository.save(doc);
        syncDocumentCount(kbId);

        // Trigger async processing AFTER transaction commits
        final Long docId = saved.getId();
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                processingService.processDocument(docId, kbId, userId);
            }
        });

        return saved;
    }

    public Document getById(Long id, Long userId) {
        Document doc = documentRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Document not found"));
        if (!doc.getKnowledgeBase().getUser().getId().equals(userId)) {
            throw new RuntimeException("Access denied");
        }
        return doc;
    }

    @Transactional
    public void delete(Long id, Long userId) throws IOException {
        Document doc = getById(id, userId);
        Path filePath = Paths.get(doc.getFilePath());
        Files.deleteIfExists(filePath);
        Long kbId = doc.getKnowledgeBase().getId();
        documentRepository.delete(doc);
        syncDocumentCount(kbId);
    }

    private void syncDocumentCount(Long kbId) {
        long count = documentRepository.countByKnowledgeBaseId(kbId);
        KnowledgeBase kb = kbRepository.findById(kbId).orElse(null);
        if (kb != null) {
            kb.setDocumentCount((int) count);
            kbRepository.save(kb);
        }
    }

    private String getFileExtension(String fileName) {
        if (fileName == null || !fileName.contains(".")) return "";
        return fileName.substring(fileName.lastIndexOf(".")).toLowerCase();
    }

    private String getFileType(String extension) {
        if (".pdf".equals(extension)) return "PDF";
        if (".doc".equals(extension) || ".docx".equals(extension)) return "WORD";
        if (".md".equals(extension) || ".markdown".equals(extension)) return "MARKDOWN";
        if (".txt".equals(extension)) return "TXT";
        if (".png".equals(extension) || ".jpg".equals(extension)
                || ".jpeg".equals(extension) || ".gif".equals(extension)
                || ".bmp".equals(extension)) return "IMAGE";
        return "OTHER";
    }
}