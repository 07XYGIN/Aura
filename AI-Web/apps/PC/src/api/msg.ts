import request from '../utils/request';

export const getMsgList = (id: string) => {
  return request({
    url: `/api/history/${id}`,
    method: 'get',
  });
};

export const delMsgList = (id: string) => {
  return request({
    url: `/api/history/${id}`,
    method: 'delete',
  });
};

export const deleteMemoryItem = (userId: string, memoryId: string) => {
  return request({
    url: `/api/user/deleteMemoryItem/${userId}/${memoryId}`,
    method: 'delete',
  });
};

export const getMemoryList = (params: { user_id: string }) => {
  return request({
    url: '/api/user/memoryList/',
    params,
  });
};
