/**
 * BeatBatch – Frontend API & Data Types
 */

export type Quality = '128' | '192' | '256' | '320';

export interface ValidLink {
  video_id: string;
  canonical_url: string;
  original_url: string;
}

export interface InvalidLine {
  line_number: number;
  text: string;
  reason: string;
}

export interface ValidateResponse {
  valid_links: ValidLink[];
  invalid_lines: InvalidLine[];
  total_valid: number;
  total_invalid: number;
}

export type JobStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed' | 'cancelled';
export type ItemStatus = 'queued' | 'downloading' | 'converting' | 'done' | 'error' | 'cancelled';

export interface JobItem {
  url: string;
  video_id: string;
  title: string | null;
  status: ItemStatus;
  percent: number;
  speed: number | null;
  eta: number | null;
  error: string | null;
  file_path: string | null;
  duration: number | null;
  filesize: number | null;
}

export interface Job {
  id: string;
  created_at: string;
  quality: string;
  status: JobStatus;
  items: JobItem[];
}

export interface CreateJobResponse {
  job_id: string;
  quality: string;
  total_valid: number;
  total_invalid: number;
  invalid_lines: InvalidLine[];
}

export type SSEEvent =
  | { event: 'connected'; job: Job }
  | { event: 'job_started'; job_id: string }
  | { event: 'item_started'; job_id: string; video_id: string; url: string }
  | {
      event: 'item_progress';
      job_id: string;
      video_id: string;
      percent: number;
      speed: number | null;
      eta: number | null;
    }
  | {
      event: 'item_finished';
      job_id: string;
      video_id: string;
      status: ItemStatus;
      title: string | null;
      percent: number;
      error: string | null;
      file_path: string | null;
      duration: number | null;
      filesize: number | null;
    }
  | { event: 'item_cancelled'; job_id: string; video_id: string }
  | { event: 'job_finished'; job_id: string; status: JobStatus };
