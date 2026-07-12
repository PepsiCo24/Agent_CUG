package com.agentcug.gateway.docling;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@Component
public class DoclingClient {

    private static final Logger log = LoggerFactory.getLogger(DoclingClient.class);
    private final WebClient webClient;

    public DoclingClient(@Value("${ai.docling.base-url}") String baseUrl,
                         ObjectMapper objectMapper) {
        this.webClient = WebClient.builder()
                .baseUrl(baseUrl)
                .build();
    }

    public Mono<String> parseDocument(String filePath) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("file", new FileSystemResource(filePath));

        return webClient.post()
                .uri("/api/v1/parse")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(builder.build()))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> {
                    JsonNode md = node.path("markdown");
                    if (!md.isMissingNode()) {
                        return md.asText();
                    }
                    JsonNode text = node.path("text");
                    if (!text.isMissingNode()) {
                        return text.asText();
                    }
                    return node.toString();
                })
                .doOnError(e -> log.error("Docling 解析失败: {}", e.getMessage()));
    }

    public Mono<String> parse(String filePath) {
        Map<String, Object> body = new HashMap<>();
        body.put("file_path", filePath);
        body.put("format", "markdown");

        return webClient.post()
                .uri("/v1/convert/file")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> node.path("document").path("text").asText(""))
                .doOnError(e -> log.error("Docling 解析失败: {}", e.getMessage()));
    }
}