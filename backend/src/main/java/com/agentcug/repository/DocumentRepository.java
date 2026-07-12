package com.agentcug.repository;

import com.agentcug.model.entity.Document;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface DocumentRepository extends JpaRepository<Document, Long> {
    List<Document> findByKnowledgeBaseId(Long kbId);
    List<Document> findByUserId(Long userId);
    long countByKnowledgeBaseId(Long kbId);
    List<Document> findByKnowledgeBaseIdAndFileNameContainingIgnoreCase(Long kbId, String keyword);

    @Modifying
    @Query("DELETE FROM Document d WHERE d.knowledgeBase.id = :kbId")
    void deleteByKnowledgeBaseId(Long kbId);
}