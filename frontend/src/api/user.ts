import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: {
    public_id: string
    username: string
    nickname: string | null
  }
}

export function loginApi(payload: LoginPayload) {
  return http.post<LoginResponse>('/users/login', payload)
}
