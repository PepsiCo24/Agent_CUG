package com.agentcug.service;

import com.agentcug.gateway.anythingllm.RagGatewayClient;
import com.agentcug.gateway.docling.DoclingClient;
import com.agentcug.repository.DocumentRepository;
import com.agentcug.model.entity.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

@Service
public class DocumentProcessingService {

    private static final Logger log = LoggerFactory.getLogger(DocumentProcessingService.class);

    private final DocumentRepository documentRepository;
    private final DoclingClient doclingClient;
    private final RagGatewayClient ragGatewayClient;

    public DocumentProcessingService(DocumentRepository documentRepository,
                                      DoclingClient doclingClient,
                                      RagGatewayClient ragGatewayClient) {
        this.documentRepository = documentRepository;
        this.doclingClient = doclingClient;
        this.ragGatewayClient = ragGatewayClient;
    }

    @Async
    public void processDocument(Long docId, Long kbId, Long userId) {
        log.info("Processing document: docId={}, kbId={}", docId, kbId);

        try {
            Document doc = documentRepository.findById(docId)
                    .orElseThrow(() -> new RuntimeException("Document not found"));

            updateParseStatus(docId, "PARSING", null);
            log.info("Step 1/2: Parsing {} (type={})", doc.getOriginalName(), doc.getFileType());

            String markdown = parseDocumentWithFallbacks(doc);

            if (markdown == null || markdown.trim().isEmpty()) {
                log.warn("Empty content after all parse attempts");
                markdown = "# " + doc.getOriginalName() + "\n\n> Unable to extract text from this file.";
                updateParseStatus(docId, "PARTIAL", markdown);
            } else {
                updateParseStatus(docId, "COMPLETED", markdown);
                log.info("Step 1/2 done: {} chars", markdown.length());
            }

            // Step 2: Embed via RAG Gateway
            updateEmbeddingStatus(docId, "PROCESSING", null);
            log.info("Step 2/2: Embedding into kbId={}", kbId);

            String ragDocId = ragGatewayClient.embedDocument(
                    String.valueOf(kbId), doc.getOriginalName(), markdown).block();

            if (ragDocId != null) {
                updateEmbeddingStatus(docId, "COMPLETED", ragDocId);
                log.info("Step 2/2 done: ragDocId={}", ragDocId);
            } else {
                updateEmbeddingStatus(docId, "FAILED", null);
                log.error("Step 2/2 failed: Gateway returned null");
            }

        } catch (Exception e) {
            log.error("Document processing failed: docId={}, error={}", docId, e.getMessage(), e);
            safeUpdateStatus(docId);
        }
    }

    private String parseDocumentWithFallbacks(Document doc) {
        String fileType = doc.getFileType() != null ? doc.getFileType().toUpperCase() : "";
        String filePath = doc.getFilePath();

        // For PDF/DOCX: use RAG Gateway parse as primary fallback (after Docling)
        // For TXT/MD: use direct file read as primary fallback
        boolean isBinaryFormat = "PDF".equals(fileType) || "WORD".equals(fileType);

        if (isBinaryFormat) {
            // Chain: RAG Gateway parse (primary) -> Docling fallback -> direct read
            return ragGatewayClient.parseDocument(filePath, fileType)
                    .onErrorResume(e -> {
                        log.warn("RAG Gateway parse failed: {}, trying Docling", e.getMessage());
                        return doclingClient.parseDocument(filePath);
                    })
                    .onErrorResume(e -> {
                        log.warn("Docling /api/v1/parse unavailable: {}", e.getMessage());
                        return doclingClient.parse(filePath);
                    })
                    .onErrorResume(e -> {
                        log.error("All parse methods failed: {}", e.getMessage());
                        return readFileAsMarkdown(doc);
                    })
                    .block();
        } else {
            // For plain text: Docling 鈫?direct read
            return doclingClient.parseDocument(filePath)
                    .onErrorResume(e -> {
                        log.warn("Docling unavailable for text file: {}", e.getMessage());
                        return readFileAsMarkdown(doc);
                    })
                    .block();
        }
    }

    private Mono<String> readFileAsMarkdown(Document doc) {
        return Mono.fromCallable(() -> {
            try {
                byte[] bytes = Files.readAllBytes(Paths.get(doc.getFilePath()));
                String content = new String(bytes, StandardCharsets.UTF_8);
                if (content == null || content.trim().isEmpty()) {
                    return "# " + doc.getOriginalName() + "\n\n> Empty file.";
                }
                return "# " + doc.getOriginalName() + "\n\n" + content;
            } catch (Exception e) {
                log.error("Failed to read file directly: {}", e.getMessage());
                return "# " + doc.getOriginalName() + "\n\n> Unable to read file content.";
            }
        });
    }

    private void updateParseStatus(Long docId, String status, String markdown) {
        try {
            Document doc = documentRepository.findById(docId).orElse(null);
            if (doc != null) {
                doc.setParseStatus(status);
                if (markdown != null) doc.setMarkdownContent(markdown);
                documentRepository.save(doc);
            }
        } catch (Exception e) {
            log.error("Failed to update parse status", e);
        }
    }

    private void updateEmbeddingStatus(Long docId, String status, String anythingllmDocId) {
        try {
            Document doc = documentRepository.findById(docId).orElse(null);
            if (doc != null) {
                doc.setEmbeddingStatus(status);
                if (anythingllmDocId != null) doc.setAnythingllmDocId(anythingllmDocId);
                documentRepository.save(doc);
            }
        } catch (Exception e) {
            log.error("Failed to update embedding status", e);
        }
    }

    private void safeUpdateStatus(Long docId) {
        try {
            Document doc = documentRepository.findById(docId).orElse(null);
            if (doc != null) {
                if (!"COMPLETED".equals(doc.getParseStatus())) doc.setParseStatus("FAILED");
                if (!"COMPLETED".equals(doc.getEmbeddingStatus())) doc.setEmbeddingStatus("FAILED");
                documentRepository.save(doc);
            }
        } catch (Exception e) {
            log.error("Failed to update status", e);
        }
    }
}
