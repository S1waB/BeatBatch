import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api/client';
import type { Quality } from './api/types';
import { BatchSummary } from './components/BatchSummary';
import { Header } from './components/Header';
import { HistoryPanel, type HistoryRecord } from './components/HistoryPanel';
import { AlertIcon } from './components/Icons';
import { ItemList } from './components/ItemList';
import { LinkInput } from './components/LinkInput';
import { ToastProvider } from './components/ToastProvider';
import { useToast } from './hooks/useToast';
import { useJobEvents } from './hooks/useJobEvents';

function BeatBatchMain() {
  const { showToast } = useToast();

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [backendHealth, setBackendHealth] = useState<'ok' | 'checking' | 'unreachable'>('checking');
  const [isStartingJob, setIsStartingJob] = useState<boolean>(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [isRetryingAll, setIsRetryingAll] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);

  // Theme management (persisted in localStorage)
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('beatbatch_theme') as 'dark' | 'light') || 'dark';
  });

  // History records (persisted in localStorage)
  const [history, setHistory] = useState<HistoryRecord[]>(() => {
    try {
      const saved = localStorage.getItem('beatbatch_history');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const {
    job,
    cancelJob,
    retryItem,
    resetJob,
  } = useJobEvents(activeJobId);

  // Apply theme to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('beatbatch_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Health check
  const checkHealth = useCallback(async () => {
    setBackendHealth('checking');
    try {
      const res = await api.checkHealth();
      setBackendHealth(res.status === 'ok' ? 'ok' : 'unreachable');
    } catch {
      setBackendHealth('unreachable');
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    api
      .checkHealth()
      .then((res) => {
        if (isMounted) {
          setBackendHealth(res.status === 'ok' ? 'ok' : 'unreachable');
        }
      })
      .catch(() => {
        if (isMounted) {
          setBackendHealth('unreachable');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Update history record when job state updates
  useEffect(() => {
    if (!job) return;

    const timer = setTimeout(() => {
      setHistory((prev) => {
        const doneCount = job.items.filter((i) => i.status === 'done').length;
        const updatedRecord: HistoryRecord = {
          id: job.id,
          createdAt: job.created_at,
          quality: job.quality,
          total: job.items.length,
          doneCount,
          status: job.status,
        };

        const existingIndex = prev.findIndex((h) => h.id === job.id);
        let newHistory: HistoryRecord[];
        if (existingIndex >= 0) {
          newHistory = [...prev];
          newHistory[existingIndex] = updatedRecord;
        } else {
          newHistory = [updatedRecord, ...prev.slice(0, 19)]; // keep last 20
        }

        try {
          localStorage.setItem('beatbatch_history', JSON.stringify(newHistory));
        } catch {
          // quota exceeded
        }
        return newHistory;
      });
    }, 0);

    return () => clearTimeout(timer);
  }, [job]);

  // Track completion toasts (only notify once per status transition)
  const lastNotifiedStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!job) {
      lastNotifiedStatus.current = null;
      return;
    }

    if (job.status !== lastNotifiedStatus.current) {
      if (job.status === 'done') {
        showToast('success', 'Batch Completed! 🎉', `All ${job.items.length} tracks are ready for download.`);
      } else if (job.status === 'partial') {
        const done = job.items.filter((i) => i.status === 'done').length;
        const err = job.items.filter((i) => i.status === 'error').length;
        showToast('error', 'Batch Finished with Errors', `${done} tracks ready, ${err} failed.`);
      } else if (job.status === 'failed') {
        showToast('error', 'Batch Failed', 'All download attempts failed.');
      } else if (job.status === 'cancelled') {
        showToast('info', 'Batch Cancelled', 'Active and pending downloads have been stopped.');
      }
      lastNotifiedStatus.current = job.status;
    }
  }, [job, showToast]);

  const handleStartJob = async (text: string, quality: Quality) => {
    setIsStartingJob(true);
    setStartError(null);
    try {
      const res = await api.createJob(text, quality);
      setActiveJobId(res.job_id);
      showToast('info', 'Download Batch Started', `Downloading ${res.total_valid} tracks at ${quality} kbps.`);
      // Clear draft once job is launched successfully
      localStorage.removeItem('beatbatch_draft');
    } catch (err) {
      if (err instanceof ApiError) {
        setStartError(err.message);
        showToast('error', 'Failed to start batch', err.message);
      } else {
        const msg = err instanceof Error ? err.message : 'Failed to start download job';
        setStartError(msg);
        showToast('error', 'Failed to start batch', msg);
      }
    } finally {
      setIsStartingJob(false);
    }
  };

  const handleNewBatch = () => {
    resetJob();
    setActiveJobId(null);
    setStartError(null);
    lastNotifiedStatus.current = null;
  };

  const handleSelectHistoryJob = (jobId: string) => {
    setActiveJobId(jobId);
    setIsHistoryOpen(false);
  };

  const handleClearHistory = () => {
    setHistory([]);
    localStorage.removeItem('beatbatch_history');
    showToast('info', 'History Cleared', 'Session history records were removed.');
  };

  // Retry all failed items in the active job
  const handleRetryAllFailed = async () => {
    if (!job) return;
    const failedIndices = job.items
      .map((item, idx) => (item.status === 'error' ? idx : -1))
      .filter((idx) => idx !== -1);

    if (failedIndices.length === 0) return;

    setIsRetryingAll(true);
    showToast('info', 'Retrying Failed Tracks', `Re-queueing ${failedIndices.length} failed items…`);

    try {
      for (const idx of failedIndices) {
        await retryItem(idx);
      }
    } catch {
      showToast('error', 'Retry encountered an error', 'Could not retry some tracks.');
    } finally {
      setIsRetryingAll(false);
    }
  };

  return (
    <div className="bb-app-layout" data-theme={theme}>
      {/* Dynamic Background Ambient Glow Orbs */}
      <div className="bb-glow-orb bb-glow-top-left" aria-hidden="true" />
      <div className="bb-glow-orb bb-glow-bottom-right" aria-hidden="true" />

      <div className="bb-container">
        <Header
          backendHealth={backendHealth}
          onCheckHealth={checkHealth}
          theme={theme}
          onToggleTheme={toggleTheme}
        >
          <HistoryPanel
            history={history}
            activeJobId={activeJobId}
            onSelectJob={handleSelectHistoryJob}
            onClearHistory={handleClearHistory}
            isOpen={isHistoryOpen}
            onToggle={() => setIsHistoryOpen((prev) => !prev)}
          />
        </Header>

        {startError && (
          <div className="bb-global-alert" role="alert">
            <AlertIcon size={18} />
            <span className="bb-alert-text">{startError}</span>
            <button
              type="button"
              className="bb-alert-close"
              onClick={() => setStartError(null)}
              aria-label="Dismiss alert"
            >
              ×
            </button>
          </div>
        )}

        {backendHealth === 'unreachable' && (
          <div className="bb-global-alert bb-alert-warning" role="alert">
            <AlertIcon size={18} />
            <span className="bb-alert-text">
              Backend is offline or unreachable at <code>http://localhost:8000</code>.
              Please start the FastAPI backend server (<code>uvicorn app.main:app --reload</code>).
            </span>
          </div>
        )}

        <main className="bb-main-content">
          {!job ? (
            <LinkInput
              onStartJob={handleStartJob}
              isStarting={isStartingJob}
              disabled={backendHealth === 'unreachable'}
            />
          ) : (
            <div className="bb-active-job-view">
              <BatchSummary
                job={job}
                onCancel={cancelJob}
                onNewBatch={handleNewBatch}
                onRetryAllFailed={handleRetryAllFailed}
                isRetryingAll={isRetryingAll}
              />
              <ItemList
                items={job.items}
                jobId={job.id}
                onRetry={retryItem}
                onRetryAllFailed={handleRetryAllFailed}
                isRetryingAll={isRetryingAll}
              />
            </div>
          )}
        </main>

        <footer className="bb-footer" role="contentinfo">
          <p>
            BeatBatch • Built with FastAPI, yt-dlp & React. Converted audio files are kept for 24h.
          </p>
        </footer>
      </div>
    </div>
  );
}

export function App() {
  return (
    <ToastProvider>
      <BeatBatchMain />
    </ToastProvider>
  );
}

export default App;
