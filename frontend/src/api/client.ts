/**
 * BeatBatch – Typed API Client
 */

import type {
  CreateJobResponse,
  Job,
  Quality,
  ValidateResponse,
} from './types';

export const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorData: unknown = null;
    try {
      errorData = await response.json();
      if (typeof errorData === 'object' && errorData !== null && 'detail' in errorData) {
        errorDetail = String((errorData as { detail: unknown }).detail);
      }
    } catch {
      // not JSON
    }
    throw new ApiError(response.status, errorDetail, errorData);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** Check health of the backend server */
  async checkHealth(): Promise<{ status: string }> {
    return request<{ status: string }>('/api/health');
  },

  /** Validate raw text with YouTube URLs */
  async validateLinks(text: string): Promise<ValidateResponse> {
    return request<ValidateResponse>('/api/validate', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  },

  /** Create a new batch download job and begin downloading */
  async createJob(text: string, quality: Quality = '192'): Promise<CreateJobResponse> {
    return request<CreateJobResponse>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ text, quality }),
    });
  },

  /** Get full state of a job (useful for sync or fallback polling) */
  async getJob(jobId: string): Promise<Job> {
    return request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`);
  },

  /** Signal a running job to cancel */
  async cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
    return request<{ job_id: string; status: string }>(
      `/api/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST' }
    );
  },

  /** Retry downloading an item in a job */
  async retryItem(jobId: string, itemIndex: number): Promise<{ job_id: string; item_index: number; status: string }> {
    return request<{ job_id: string; item_index: number; status: string }>(
      `/api/jobs/${encodeURIComponent(jobId)}/items/${itemIndex}/retry`,
      { method: 'POST' }
    );
  },

  /** URL to download single MP3 file */
  getFileDownloadUrl(jobId: string, itemIndex: number): string {
    return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/files/${itemIndex}`;
  },

  /** URL to download all completed tracks as a ZIP */
  getZipDownloadUrl(jobId: string): string {
    return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/zip`;
  },

  /** URL to SSE event stream */
  getEventsUrl(jobId: string): string {
    return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/events`;
  },
};
