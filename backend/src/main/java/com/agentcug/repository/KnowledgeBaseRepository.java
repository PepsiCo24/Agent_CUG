package com.agentcug.repository;

import com.agentcug.model.entity.KnowledgeBase;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface KnowledgeBaseRepository extends JpaRepository<KnowledgeBase, Long> {
    List<KnowledgeBase> findByUserId(Long userId);
    boolean existsByUserIdAndName(Long userId, String name);
}