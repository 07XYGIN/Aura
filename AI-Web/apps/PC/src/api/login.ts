import request from '../utils/request';
export interface registerForm {
  username: string | undefined;
  password: string;
  newPassword: string | undefined;
  code?: string;
}

export interface loginForm {
  username: string | undefined;
  password: string | undefined;
  code?: string | undefined;
}

export interface LoginResponse {
  code?: number;
  data?: string;
  token?: string;
  message?: string;
  msg?: string;
}

export const register = (register: registerForm) => {
  const { newPassword: _newPassword, code: _code, ...body } = register;
  return request({
    url: '/api/user/register',
    method: 'POST',
    data: body,
  });
};

export const login = (login: loginForm): Promise<LoginResponse> => {
  const { code: _code, ...body } = login;
  return request({
    url: '/api/user/login',
    method: 'POST',
    data: body,
  });
};
