import request from "@/utils/requests";

export interface MemoryMetadata {
  title?: string;
  content?: string;
  create_time?: string;
  user_id?: string;
}

export interface MemoryDocument {
  id: string;
  metadata: MemoryMetadata;
  page_content: string;
  type: "Document";
}

export interface MemoryPage {
  items: MemoryDocument[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export const getMemoryList = (params: { page: number; pageSize: number }) => {
  return request<MemoryPage>({
    url: "/api/user/memoryList",
    method: "GET",
    params,
  });
};
