package com.agentcug.model.dto;

import javax.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatRequest {
    @NotBlank(message = "问题不能为空")
    private String question;

    private String conversationId;
}