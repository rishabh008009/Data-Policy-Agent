/**
 * Axios client instance for API communication.
 */

import axios, { type AxiosError, type AxiosInstance, type AxiosResponse } from 'axios';
import type { ApiError } from './types';

// Base URL for the API - use relative URL for production (same origin), absolute for dev
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Create and configure the axios instance.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

/**
 * Request interceptor for logging and adding auth headers if needed.
 */
apiClient.interceptors.request.use(
  (config) => {
    // Add any auth headers here if needed in the future
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for error handling.
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError<ApiError>) => {
    // Extract error message from response
    const errorMessage = error.response?.data?.detail || error.message || 'An unexpected error occurred';
    
    // Create a standardized error object
    const apiError: ApiError = {
      detail: errorMessage,
      status_code: error.response?.status,
    };

    // Log error for debugging
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      message: errorMessage,
    });

    return Promise.reject(apiError);
  }
);

export default apiClient;

/**
 * Helper function to handle API responses.
 */
export async function handleApiResponse<T>(promise: Promise<AxiosResponse<T>>): Promise<T> {
  const response = await promise;
  return response.data;
}

/**
 * Helper function to build query string from filter object.
 */
export function buildQueryParams(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  });
  
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}
