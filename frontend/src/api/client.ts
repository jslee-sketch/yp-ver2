import axios from 'axios';

// 개발: vite proxy 사용 (/api → localhost:9000)
// 프로덕션: VITE_API_URL 환경변수 사용, 빈 값이면 같은 도메인 (Railway 등)
const API_BASE_URL = import.meta.env.DEV
  ? '/api'
  : (import.meta.env.VITE_API_URL || '');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터: JWT 토큰 자동 첨부
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터: 401 → 로그인 리다이렉트
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// OAuth2PasswordRequestForm: application/x-www-form-urlencoded + username 필드
export async function loginApi(email: string, password: string) {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  return apiClient.post('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

export async function sellerLoginApi(email: string, password: string) {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  return apiClient.post('/auth/seller/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

export default apiClient;
