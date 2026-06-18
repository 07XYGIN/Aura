import request from '../utils/request';

export const getUserInfo = () => {
  return request({
    url: '/api/user/userInfo',
    method: 'get',
  });
};

export const updateUserInfo = (data: unknown) => {
  return request({
    url: '/api/user/updateInfo',
    method: 'put',
    data,
  });
};

export const deleteUser = (username: string) => {
  return request({
    url: `/api/user/${encodeURIComponent(username)}`,
    method: 'delete',
  });
};
