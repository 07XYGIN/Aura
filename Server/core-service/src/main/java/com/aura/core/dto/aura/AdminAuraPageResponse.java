package com.aura.core.dto.aura;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class AdminAuraPageResponse {
    private List<Map<String, Object>> items;
    private long total;
    private int page;
    private int pageSize;
}
