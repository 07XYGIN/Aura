import request from '../utils/request';

export const getMsgList = (id?: string) => {
  return request({
    url: `/api/history/${encodeURIComponent(id ?? 'current')}`,
    method: 'get',
  });
};

export const delMsgList = (id?: string) => {
  return request({
    url: `/api/history/${encodeURIComponent(id ?? 'current')}`,
    method: 'delete',
  });
};

export const deleteMemoryItem = (_userId: string, memoryId: string) => {
  return request({
    url: `/api/memory/${encodeURIComponent(memoryId)}`,
    method: 'delete',
  });
};

export const getMemoryList = (params?: { page?: number; pageSize?: number }) => {
  return request({
    url: '/api/memory/list',
    method: 'get',
    params,
  });
};
