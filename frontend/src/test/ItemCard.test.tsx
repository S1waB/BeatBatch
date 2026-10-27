import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobItem } from '../api/types';
import { ItemCard } from '../components/ItemCard';

describe('ItemCard Component', () => {
  const onRetryMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders downloading state with progress bar, speed, and ETA', () => {
    const item: JobItem = {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcY',
      video_id: 'dQw4w9WgXcY',
      title: 'Never Gonna Give You Up',
      status: 'downloading',
      percent: 45.5,
      speed: 2500000,
      eta: 12,
      error: null,
      file_path: null,
      duration: 212,
      filesize: 3500000,
    };

    render(
      <ItemCard
        item={item}
        index={0}
        jobId="test-job-uuid"
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByText('Never Gonna Give You Up')).toBeInTheDocument();
    expect(screen.getByText('Downloading')).toBeInTheDocument();
    expect(screen.getByText('45.5%')).toBeInTheDocument();
    expect(screen.getByText(/2.4 MB\/s/i)).toBeInTheDocument();
    expect(screen.getByText(/ETA 12s/i)).toBeInTheDocument();

    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '46');
  });

  it('renders done state with Download MP3 button', () => {
    const item: JobItem = {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcY',
      video_id: 'dQw4w9WgXcY',
      title: 'Never Gonna Give You Up',
      status: 'done',
      percent: 100,
      speed: null,
      eta: null,
      error: null,
      file_path: 'downloads/test.mp3',
      duration: 212,
      filesize: 4200000,
    };

    render(
      <ItemCard
        item={item}
        index={0}
        jobId="test-job-uuid"
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByText('Done')).toBeInTheDocument();
    const downloadLink = screen.getByRole('link', { name: /Download MP3/i });
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink).toHaveAttribute(
      'href',
      expect.stringContaining('/api/jobs/test-job-uuid/files/0')
    );
  });

  it('renders error state with message and Retry button', async () => {
    const item: JobItem = {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcY',
      video_id: 'dQw4w9WgXcY',
      title: null,
      status: 'error',
      percent: 0,
      speed: null,
      eta: null,
      error: 'Video is unavailable in your region',
      file_path: null,
      duration: null,
      filesize: null,
    };

    render(
      <ItemCard
        item={item}
        index={1}
        jobId="test-job-uuid"
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Video is unavailable in your region')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    expect(retryBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(retryBtn);
    });
    expect(onRetryMock).toHaveBeenCalledWith(1);
  });
});
