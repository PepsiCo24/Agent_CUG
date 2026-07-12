package com.agentcug.gateway.anythingllm;

import com.agentcug.model.dto.ChatResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.*;

@Component
public class RagGatewayClient {

    private static final Logger log = LoggerFactory.getLogger(RagGatewayClient.class);
    private final WebClient webClient;
    private final ObjectMapper objectMapper;

    public RagGatewayClient(@Value("${ai.rag-gateway.base-url:http://localhost:3001}") String baseUrl,
                             ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.webClient = WebClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    public Mono<Boolean> healthCheck() {
        return webClient.get()
                .uri("/health")
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> "ok".equals(node.path("status").asText()))
                .onErrorReturn(false);
    }

    /**
     * Parse PDF/DOCX via RAG Gateway (replaces Docling)
     */
    public Mono<String> parseDocument(String filePath, String fileType) {
        Map<String, Object> body = new HashMap<>();
        body.put("file_path", filePath);
        body.put("file_type", fileType);

        return webClient.post()
                .uri("/api/rag/parse")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> {
                    if (node.path("success").asBoolean(false)) {
                        return node.path("markdown").asText("");
                    }
                    return "";
                })
                .doOnError(e -> log.error("RAG parse failed: {}", e.getMessage()))
                .onErrorReturn("");
    }

    public Mono<String> embedDocument(String kbId, String documentName, String markdownContent) {
        Map<String, Object> body = new HashMap<>();
        body.put("kb_id", kbId);
        body.put("document_name", documentName);
        body.put("markdown_content", markdownContent);

        return webClient.post()
                .uri("/api/rag/embed")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> node.path("doc_id").asText())
                .doOnError(e -> log.error("Document embedding failed: {}", e.getMessage()));
    }

    public Mono<ChatResponse> chat(String kbId, String question, List<Map<String, String>> history) {
        Map<String, Object> body = new HashMap<>();
        body.put("kb_id", kbId);
        body.put("question", question);

        List<Map<String, String>> historyList = new ArrayList<>();
        if (history != null) {
            historyList.addAll(history);
        }
        body.put("history", historyList);

        return webClient.post()
                .uri("/api/rag/chat")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(this::parseChatResponse)
                .doOnError(e -> log.error("RAG chat failed: {}", e.getMessage()));
    }

    private ChatResponse parseChatResponse(JsonNode node) {
        String answer = node.path("answer").asText("");

        List<ChatResponse.Citation> citations = new ArrayList<>();
        JsonNode cites = node.path("citations");
        if (cites.isArray()) {
            for (JsonNode c : cites) {
                citations.add(ChatResponse.Citation.builder()
                        .documentName(c.path("document_name").asText(""))
                        .snippet(c.path("snippet").asText(""))
                        .pageNumber(0)
                        .build());
            }
        }

        return ChatResponse.builder()
                .answer(answer)
                .conversationId(node.path("conversation_id").asText("default"))
                .citations(citations)
                .tokensUsed(0)
                .build();
    }
}