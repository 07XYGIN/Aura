package com.aura.core.entity;

import lombok.Data;

@Data
public class LangchainPgEmbedding {
    private String id;
    private String collectionId;
    private String embedding;
    private String document;
    private String cmetadata;
}
