import axios from 'axios'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

// 请求拦截器：自动携带 Token
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

let refreshPromise = null

// 使用原始 axios 刷新令牌, 避免进入拦截器造成死循环
async function refreshAccessToken() {
  const refresh_token = localStorage.getItem('refresh_token')
  if (!refresh_token) {
    throw new Error('缺少刷新令牌')
  }
  const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token })
  const payload = data?.data
  if (!payload?.access_token) {
    throw new Error('刷新令牌失败')
  }
  localStorage.setItem('token', payload.access_token)
  if (payload.refresh_token) {
    localStorage.setItem('refresh_token', payload.refresh_token)
  }
  return payload.access_token
}

function redirectToLogin() {
  // 清空本地令牌; 跳转会触发整页刷新, Pinia 状态随之重置
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

// 响应拦截器：统一解析 {code, message, data}, 并处理 401 自动刷新
request.interceptors.response.use(
  response => {
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 200) {
        return body.data
      }
      return Promise.reject({
        status: body.code,
        message: body.message || '请求失败',
        raw: response
      })
    }
    // 兼容未包装的响应
    return body
  },
  async error => {
    const originalRequest = error.config
    const status = error.response?.status

    // 401 且未重试过, 则尝试刷新令牌后重放请求
    if (status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null
          })
        }
        const newToken = await refreshPromise
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return request(originalRequest)
      } catch (refreshError) {
        redirectToLogin()
        return Promise.reject({
          status,
          message: '登录已过期, 请重新登录',
          raw: error
        })
      }
    }

    // 统一错误消息
    const detail = error.response?.data?.message || error.response?.data?.detail || ''
    let message = '网络异常, 请稍后再试'

    switch (status) {
      case 400:
        message = detail || '请求参数有误'
        break
      case 401:
        message = '登录已过期, 请重新登录'
        break
      case 403:
        message = detail || '您没有权限执行此操作'
        break
      case 404:
        message = detail || '请求的资源不存在'
        break
      case 422:
        message = detail || '输入信息格式不正确, 请检查后重试'
        break
      case 500:
      case 502:
      case 503:
        message = '服务器繁忙, 请稍后再试'
        break
    }

    return Promise.reject({
      status,
      message,
      raw: error
    })
  }
)

export default request
