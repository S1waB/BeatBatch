import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Job, SSEEvent } from '../api/types';

interface UseJobEventsReturn {
  job: Job | null;
  isConnected: boolean;
  error: string | null;
  cancelJob: () => Promise<void>;
  retryItem: (itemIndex: number) => Promise<void>;
  resetJob: () => void;
  refreshJob: () => Promise<void>;
}

export function useJobEvents(jobId: string | null): UseJobEventsReturn {
  const [job, setJob] = useState<Job | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchJobSnapshot = useCallback(async (id: string) => {
    try {
      const data = await api.getJob(id);
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job');
    }
  }, []);

  const refreshJob = useCallback(async () => {
    if (jobId) {
      await fetchJobSnapshot(jobId);
    }
  }, [jobId, fetchJobSnapshot]);

  const resetJob = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setJob(null);
    setIsConnected(false);
    setError(null);
  }, []);

  const cancelJob = useCallback(async () => {
    if (!jobId) return;
    try {
      await api.cancelJob(jobId);
      // Immediately reflect cancelling locally
      setJob((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          status: 'cancelled',
          items: prev.items.map((it) =>
            it.status === 'queued' ? { ...it, status: 'cancelled' } : it
          ),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    }
  }, [jobId]);

  const retryItem = useCallback(
    async (itemIndex: number) => {
      if (!jobId) return;
      try {
        await api.retryItem(jobId, itemIndex);
        setJob((prev) => {
          if (!prev) return prev;
          const updated = [...prev.items];
          if (updated[itemIndex]) {
            updated[itemIndex] = {
              ...updated[itemIndex],
              status: 'queued',
              percent: 0,
              error: null,
              speed: null,
              eta: null,
            };
          }
          return {
            ...prev,
            status: 'running',
            items: updated,
          };
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to retry item');
      }
    },
    [jobId]
  );

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let isMounted = true;
    // Fetch initial snapshot
    api
      .getJob(jobId)
      .then((data) => {
        if (isMounted) setJob(data);
      })
      .catch((err) => {
        if (isMounted) setError(err instanceof Error ? err.message : 'Failed to fetch job');
      });

    // Connect to SSE stream
    const eventsUrl = api.getEventsUrl(jobId);
    const es = new EventSource(eventsUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setIsConnected(false);
      // EventSource will automatically attempt reconnection.
    };

    es.onmessage = (messageEvent) => {
      try {
        const data = JSON.parse(messageEvent.data) as SSEEvent;

        if (data.event === 'connected') {
          setJob(data.job);
        } else if (data.event === 'job_started') {
          setJob((prev) => (prev ? { ...prev, status: 'running' } : prev));
        } else if (data.event === 'item_started') {
          setJob((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              items: prev.items.map((item) =>
                item.video_id === data.video_id
                  ? { ...item, status: 'downloading', percent: 0 }
                  : item
              ),
            };
          });
        } else if (data.event === 'item_progress') {
          setJob((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              items: prev.items.map((item) => {
                if (item.video_id !== data.video_id) return item;
                const isConverting = data.percent >= 99 && item.status !== 'done';
                return {
                  ...item,
                  percent: data.percent,
                  speed: data.speed,
                  eta: data.eta,
                  status: isConverting ? 'converting' : 'downloading',
                };
              }),
            };
          });
        } else if (data.event === 'item_finished') {
          setJob((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              items: prev.items.map((item) => {
                if (item.video_id !== data.video_id) return item;
                return {
                  ...item,
                  status: data.status,
                  title: data.title ?? item.title,
                  percent: data.percent,
                  error: data.error,
                  file_path: data.file_path,
                  duration: data.duration,
                  filesize: data.filesize,
                  speed: null,
                  eta: null,
                };
              }),
            };
          });
        } else if (data.event === 'item_cancelled') {
          setJob((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              items: prev.items.map((item) =>
                item.video_id === data.video_id
                  ? { ...item, status: 'cancelled' }
                  : item
              ),
            };
          });
        } else if (data.event === 'job_finished') {
          setJob((prev) => (prev ? { ...prev, status: data.status } : prev));
          // Once the entire job is finished, the backend terminates the event stream
          es.close();
          setIsConnected(false);
        }
      } catch {
        // Ignored or non-JSON keepalive comment
      }
    };

    return () => {
      isMounted = false;
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [jobId, fetchJobSnapshot, resetJob]);

  return {
    job,
    isConnected,
    error,
    cancelJob,
    retryItem,
    resetJob,
    refreshJob,
  };
}
