export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  cache?: RequestCache
  next?: { revalidate?: number }
}

export type ApiResponse<T = unknown> = {
  code: number
  message?: string
  msg?: string
  data?: T
  token?: string
}
