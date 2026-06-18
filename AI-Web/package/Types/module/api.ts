export type ApiResponse<T = unknown> = {
    code: number
    message?: string
    msg?: string
    data?: T
    token?: string
}

export type PageResult<T> = {
    items: T[]
    total: number
    page: number
    pageSize: number
    hasMore?: boolean
}
