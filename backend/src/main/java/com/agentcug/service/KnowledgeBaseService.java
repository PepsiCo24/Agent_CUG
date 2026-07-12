package com.agentcug.service;

import com.agentcug.model.dto.KnowledgeBaseDTO;
import com.agentcug.model.entity.Document;
import com.agentcug.model.entity.KnowledgeBase;
import com.agentcug.model.entity.User;
import com.agentcug.repository.ChatMessageRepository;
import com.agentcug.repository.DocumentRepository;
import com.agentcug.repository.KnowledgeBaseRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

@Service
public class KnowledgeBaseService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseService.class);

    private final KnowledgeBaseRepository kbRepository;
    private final DocumentRepository documentRepository;
    private final ChatMessageRepository chatMessageRepository;

    public KnowledgeBaseService(KnowledgeBaseRepository kbRepository,
                                 DocumentRepository documentRepository,
                                 ChatMessageRepository chatMessageRepository) {
        this.kbRepository = kbRepository;
        this.documentRepository = documentRepository;
        this.chatMessageRepository = chatMessageRepository;
    }

    public List<KnowledgeBase> listByUser(Long userId) {
        return kbRepository.findByUserId(userId);
    }

    public KnowledgeBase getById(Long id, Long userId) {
        KnowledgeBase kb = kbRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Knowledge base not found"));
        if (!kb.getUser().getId().equals(userId)) {
            throw new RuntimeException("Access denied");
        }
        return kb;
    }

    public KnowledgeBase create(KnowledgeBaseDTO dto, User user) {
        if (kbRepository.existsByUserIdAndName(user.getId(), dto.getName())) {
            throw new RuntimeException("Knowledge base name already exists");
        }

        KnowledgeBase kb = KnowledgeBase.builder()
                .name(dto.getName())
                .description(dto.getDescription())
                .user(user)
                .documentCount(0)
                .build();

        kb = kbRepository.save(kb);
        log.info("Knowledge base created: {} (id={})", kb.getName(), kb.getId());
        return kb;
    }

    public KnowledgeBase update(Long id, KnowledgeBaseDTO dto, Long userId) {
        KnowledgeBase kb = getById(id, userId);

        if (!kb.getName().equals(dto.getName())
                && kbRepository.existsByUserIdAndName(userId, dto.getName())) {
            throw new RuntimeException("Knowledge base name already exists");
        }

        kb.setName(dto.getName());
        kb.setDescription(dto.getDescription());
        return kbRepository.save(kb);
    }

    @Transactional
    public void delete(Long id, Long userId) throws IOException {
        KnowledgeBase kb = getById(id, userId);
        log.info("Deleting knowledge base: {} (id={})", kb.getName(), kb.getId());

        // 1. Delete document files from disk
        List<Document> docs = documentRepository.findByKnowledgeBaseId(id);
        for (Document doc : docs) {
            try {
                Files.deleteIfExists(Paths.get(doc.getFilePath()));
            } catch (IOException e) {
                log.warn("Failed to delete file: {}", doc.getFilePath());
            }
        }

        // 2. Delete documents from DB
        documentRepository.deleteByKnowledgeBaseId(id);

        // 3. Delete chat messages
        chatMessageRepository.deleteByKnowledgeBaseId(id);

        // 4. Delete KB itself
        kbRepository.delete(kb);

        log.info("Knowledge base deleted successfully: id={}", id);
    }
}