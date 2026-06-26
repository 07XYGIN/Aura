package com.aura.core.dto.table;

import lombok.Data;

@Data
public class LangchainPgEmbeddingDto {
    private String id;
    private String collectionId;
    private String embedding;
    private String document;
    private String cmetadata;
}
