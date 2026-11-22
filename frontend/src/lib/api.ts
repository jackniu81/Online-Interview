import axios from 'axios'

/** Shared axios instance; vite dev server proxies /api to the backend. */
export const api = axios.create({ baseURL: '/api' })

const TOKEN_KEY = 'admin_token'

export function getAdminToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAdminToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

api.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const url: string = error.config?.url ?? ''
    // the login endpoint's own 401 must not trigger a redirect (would wipe the error message)
    if (
      error.response?.status === 401 &&
      window.location.pathname.startsWith('/admin') &&
      !url.includes('/admin/login')
    ) {
      setAdminToken(null)
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  },
)
