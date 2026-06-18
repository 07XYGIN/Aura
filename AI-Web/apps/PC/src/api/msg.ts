import request from '../utils/request';

export const getMsgList = (_id?: string) => {
  return request({
    url: '/api/aura/sessions/current/messages',
    method: 'get',
  });
};

export const delMsgList = (_id?: string) => {
  return request({
    url: '/api/aura/sessions/current/messages',
    method: 'delete',
  });
};

export const deleteMemoryItem = (_userId: string, memoryId: string) => {
  return request({
    url: `/api/aura/memories/${encodeURIComponent(memoryId)}`,
    method: 'delete',
  });
};

export const getMemoryList = (params?: { page?: number; pageSize?: number }) => {
  return request({
    url: '/api/aura/memories',
    method: 'get',
    params,
  });
};
