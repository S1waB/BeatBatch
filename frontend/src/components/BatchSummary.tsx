import React from 'react';
import { api } from '../api/client';
import type { Job } from '../api/types';
import {
  CancelIcon,
  CheckIcon,
  RetryIcon,
  SpinnerIcon,
  ZipIcon,
} from './Icons';

interface BatchSummaryProps {
  job: Job;
  onCancel: () => Promise<void>;
  onNewBatch: () => void;
  onRetryAllFailed?: () => Promise<void>;
  isCancelling?: boolean;
  isRetryingAll?: boolean;
}

export const BatchSummary: React.FC<BatchSummaryProps> = ({
  job,
  onCancel,
  onNewBatch,
  onRetryAllFailed,
  isCancelling = false,
  isRetryingAll = false,
}) => {
  const total = job.items.length;
  const doneCount = job.items.filter((i) => i.status === 'done').length;
  const errorCount = job.items.filter((i) => i.status === 'error').length;
  const downloadingCount = job.items.filter(
    (i) => i.status === 'downloading' || i.status === 'converting'
  ).length;

  // Calculate weighted global progress
  const totalPercentSum = job.items.reduce((acc, it) => acc + (it.percent || 0), 0);
  const globalPercent = total > 0 ? Math.min(100, Math.round(totalPercentSum / total)) : 0;

  const isRunning = job.status === 'running' || job.status === 'queued';
  const isFinished = ['done', 'partial', 'failed', 'cancelled'].includes(job.status);
  const canDownloadZip = doneCount > 0 && isFinished;

  const zipUrl = api.getZipDownloadUrl(job.id);

  return (
    <div className="bb-batch-summary" role="region" aria-label="Batch Download Status">
      <div className="bb-summary-top">
        <div className="bb-summary-title-col">
          <div className="bb-summary-status-row">
            <h2 className="bb-summary-title">Batch Progress</h2>
            <span
              className={`bb-status-pill bb-status-${job.status}`}
              role="status"
              aria-label={`Batch status: ${job.status}`}
            >
              {isRunning && <SpinnerIcon size={12} className="bb-spin-inline" />}
              {job.status.toUpperCase()}
            </span>
            <span className="bb-quality-tag">{job.quality} kbps</span>
          </div>
          <p className="bb-summary-subtitle" aria-live="polite">
            {isRunning && `Processing ${downloadingCount} active of ${total} tracks…`}
            {job.status === 'done' && `All ${total} tracks downloaded successfully!`}
            {job.status === 'partial' && `${doneCount} completed, ${errorCount} had errors.`}
            {job.status === 'failed' && `Batch failed. Review error messages below.`}
            {job.status === 'cancelled' && `Batch was cancelled.`}
          </p>
        </div>

        <div className="bb-summary-actions">
          {/* Retry all failed button */}
          {errorCount > 0 && onRetryAllFailed && (
            <button
              type="button"
              className="bb-btn bb-btn-retry-all"
              onClick={onRetryAllFailed}
              disabled={isRetryingAll}
              title={`Retry all ${errorCount} failed downloads`}
              aria-label={`Retry all ${errorCount} failed tracks`}
            >
              {isRetryingAll ? (
                <>
                  <SpinnerIcon size={15} />
                  <span>Retrying All…</span>
                </>
              ) : (
                <>
                  <RetryIcon size={15} />
                  <span>Retry All Failed ({errorCount})</span>
                </>
              )}
            </button>
          )}

          {/* Cancel button */}
          {isRunning && (
            <button
              type="button"
              className="bb-btn bb-btn-danger"
              onClick={onCancel}
              disabled={isCancelling}
              title="Stop remaining downloads"
              aria-label="Cancel active batch downloads"
            >
              <CancelIcon size={16} />
              <span>{isCancelling ? 'Cancelling…' : 'Cancel Batch'}</span>
            </button>
          )}

          {/* Download ZIP */}
          {canDownloadZip && (
            <a
              href={zipUrl}
              download
              className="bb-btn bb-btn-primary bb-btn-zip"
              title="Download all converted MP3s in a single ZIP archive"
              aria-label={`Download all ${doneCount} MP3 tracks as a ZIP archive`}
            >
              <ZipIcon size={16} />
              <span>Download ZIP ({doneCount})</span>
            </a>
          )}

          {/* New Batch */}
          {isFinished && (
            <button
              type="button"
              className="bb-btn bb-btn-secondary"
              onClick={onNewBatch}
              aria-label="Start a new download batch"
            >
              <span>+ New Batch</span>
            </button>
          )}
        </div>
      </div>

      {/* Global Progress Bar with a11y */}
      <div className="bb-global-progress-wrap">
        <div
          className="bb-global-progress-track"
          role="progressbar"
          aria-valuenow={globalPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Overall batch download progress"
        >
          <div
            className={`bb-global-progress-bar ${
              isRunning ? 'bb-bar-animated' : ''
            } ${job.status === 'done' ? 'bb-bar-complete' : ''}`}
            style={{ width: `${globalPercent}%` }}
          />
        </div>
        <div className="bb-global-progress-meta">
          <span className="bb-progress-pct" aria-live="polite">
            {globalPercent}% completed
          </span>
          <span className="bb-progress-counts">
            <strong className="text-done">{doneCount}</strong> done •{' '}
            {errorCount > 0 && <strong className="text-error">{errorCount} error • </strong>}
            <span className="text-total">{total} total</span>
          </span>
        </div>
      </div>

      {/* Metric Quick Stats */}
      <div className="bb-stats-grid">
        <div className="bb-stat-card">
          <span className="bb-stat-label">Total Tracks</span>
          <span className="bb-stat-value">{total}</span>
        </div>
        <div className="bb-stat-card bb-stat-done">
          <span className="bb-stat-label">Successful</span>
          <span className="bb-stat-value">
            <CheckIcon size={15} />
            {doneCount}
          </span>
        </div>
        <div className="bb-stat-card bb-stat-active">
          <span className="bb-stat-label">In Progress</span>
          <span className="bb-stat-value">{downloadingCount}</span>
        </div>
        <div className="bb-stat-card bb-stat-error">
          <span className="bb-stat-label">Errors</span>
          <span className="bb-stat-value">{errorCount}</span>
        </div>
      </div>
    </div>
  );
};
