package com.agentcug.service;

import com.agentcug.model.entity.ChatMessage;
import com.agentcug.model.entity.KnowledgeBase;
import com.agentcug.repository.ChatMessageRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ChatService {

    private final ChatMessageRepository chatMessageRepository;
    private final KnowledgeBaseService kbService;

    public ChatService(ChatMessageRepository chatMessageRepository,
                       KnowledgeBaseService kbService) {
        this.chatMessageRepository = chatMessageRepository;
        this.kbService = kbService;
    }

    public Page<ChatMessage> getHistory(Long kbId, Long userId, int page, int size) {
        kbService.getById(kbId, userId);
        return chatMessageRepository.findByKnowledgeBaseIdAndUserIdOrderByCreatedAtAsc(
                kbId, userId, PageRequest.of(page, size));
    }

    public ChatMessage saveMessage(Long kbId, Long userId, String role, String content, String citations) {
        KnowledgeBase kb = kbService.getById(kbId, userId);
        ChatMessage message = ChatMessage.builder()
                .knowledgeBase(kb)
                .user(kb.getUser())
                .role(role)
                .content(content)
                .citations(citations)
                .build();
        return chatMessageRepository.save(message);
    }

    public List<ChatMessage> getConversationHistory(Long kbId, Long userId) {
        return chatMessageRepository.findByKnowledgeBaseIdAndUserIdOrderByCreatedAtAsc(kbId, userId);
    }

    @Transactional
    public void clearHistory(Long kbId, Long userId) {
        kbService.getById(kbId, userId);
        chatMessageRepository.deleteByKnowledgeBaseIdAndUserId(kbId, userId);
    }
}