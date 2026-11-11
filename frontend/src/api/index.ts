// .env의 VITE_API_MODE 값으로 가짜/진짜 서버를 고른다. 기본은 mock.
import { httpApi } from './http';
import { mockApi } from './mock';

export const api = import.meta.env.VITE_API_MODE === 'http' ? httpApi : mockApi;
export const API_MODE: 'mock' | 'http' = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock';
