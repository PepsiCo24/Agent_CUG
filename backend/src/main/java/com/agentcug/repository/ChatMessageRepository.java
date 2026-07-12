package com.agentcug.repository;

import com.agentcug.model.entity.ChatMessage;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
    Page<ChatMessage> findByKnowledgeBaseIdAndUserIdOrderByCreatedAtAsc(
            Long kbId, Long userId, Pageable pageable);
    List<ChatMessage> findByKnowledgeBaseIdAndUserIdOrderByCreatedAtAsc(
            Long kbId, Long userId);
    void deleteByKnowledgeBaseId(Long kbId);

    @Modifying
    @Query("DELETE FROM ChatMessage m WHERE m.knowledgeBase.id = :kbId AND m.user.id = :userId")
    void deleteByKnowledgeBaseIdAndUserId(Long kbId, Long userId);
}