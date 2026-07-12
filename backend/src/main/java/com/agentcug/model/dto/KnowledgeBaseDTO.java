package com.agentcug.model.dto;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import lombok.Data;

@Data
public class KnowledgeBaseDTO {
    @NotBlank(message = "知识库名称不能为空")
    @Size(max = 100)
    private String name;

    @Size(max = 500)
    private String description;
}