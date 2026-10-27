import React, { useState } from 'react';
import { api } from '../api/client';
import type { JobItem } from '../api/types';
import {
  formatBytes,
  formatDuration,
  formatEta,
  formatSpeed,
} from '../utils/formatters';
import {
  AlertIcon,
  CheckIcon,
  DownloadIcon,
  MusicIcon,
  RetryIcon,
  SpinnerIcon,
  YouTubeIcon,
} from './Icons';

interface ItemCardProps {
  item: JobItem;
  index: number;
  jobId: string;
  onRetry: (index: number) => Promise<void>;
}

export const ItemCard: React.FC<ItemCardProps> = ({
  item,
  index,
  jobId,
  onRetry,
}) => {
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await onRetry(index);
    } finally {
      setIsRetrying(false);
    }
  };

  const downloadUrl = api.getFileDownloadUrl(jobId, index);

  // Status mapping
  const isQueued = item.status === 'queued';
  const isDownloading = item.status === 'downloading';
  const isConverting = item.status === 'converting' || (item.percent >= 99 && item.status !== 'done');
  const isDone = item.status === 'done';
  const isError = item.status === 'error';
  const isCancelled = item.status === 'cancelled';

  const displayTitle = item.title || item.url || `Track #${index + 1}`;
  const displaySpeed = formatSpeed(item.speed);
  const displayEta = formatEta(item.eta);
  const displaySize = formatBytes(item.filesize);
  const displayDuration = formatDuration(item.duration);

  return (
    <div
      className={`bb-item-card bb-item-${item.status}`}
      id={`item-card-${index}`}
    >
      <div className="bb-item-main">
        {/* Left column: Number + Audio / YT Icon */}
        <div className="bb-item-badge-wrap">
          <span className="bb-item-index">#{index + 1}</span>
          <div className="bb-item-thumb">
            {isDone ? (
              <MusicIcon size={20} className="bb-thumb-icon bb-thumb-done" />
            ) : isError ? (
              <AlertIcon size={20} className="bb-thumb-icon bb-thumb-error" />
            ) : (
              <YouTubeIcon size={20} className="bb-thumb-icon" />
            )}
          </div>
        </div>

        {/* Center column: Title, URL, Status Badge, Metrics */}
        <div className="bb-item-content">
          <div className="bb-item-row-top">
            <h3 className="bb-item-title" title={displayTitle}>
              {displayTitle}
            </h3>

            <div className="bb-item-badges">
              {isQueued && <span className="bb-badge bb-badge-queued">Queued</span>}
              {isDownloading && (
                <span className="bb-badge bb-badge-downloading">
                  <SpinnerIcon size={12} className="bb-spin-inline" />
                  Downloading
                </span>
              )}
              {isConverting && (
                <span className="bb-badge bb-badge-converting">
                  <SpinnerIcon size={12} className="bb-spin-inline" />
                  Converting
                </span>
              )}
              {isDone && (
                <span className="bb-badge bb-badge-done">
                  <CheckIcon size={13} />
                  Done
                </span>
              )}
              {isError && (
                <span className="bb-badge bb-badge-error">
                  <AlertIcon size={13} />
                  Error
                </span>
              )}
              {isCancelled && <span className="bb-badge bb-badge-cancelled">Cancelled</span>}
            </div>
          </div>

          <div className="bb-item-submeta">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="bb-item-link"
              title="Open YouTube video in new tab"
            >
              {item.video_id ? `youtube.com/watch?v=${item.video_id}` : item.url}
            </a>

            {displayDuration && (
              <span className="bb-meta-pill bb-meta-duration">
                ⏱ {displayDuration}
              </span>
            )}
            {displaySize && displaySize !== '0 B' && (
              <span className="bb-meta-pill bb-meta-size">
                💾 {displaySize}
              </span>
            )}
          </div>

          {/* Progress bar (shown when queued, downloading, or converting) */}
          {(isDownloading || isConverting || isQueued) && (
            <div className="bb-item-progress-section">
              <div
                className="bb-item-progress-track"
                role="progressbar"
                aria-valuenow={Math.round(item.percent)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Progress for ${displayTitle}: ${item.percent.toFixed(1)}%`}
              >
                <div
                  className={`bb-item-progress-bar ${
                    isConverting ? 'bb-bar-converting' : ''
                  }`}
                  style={{ width: `${Math.max(3, item.percent)}%` }}
                />
              </div>

              <div className="bb-item-progress-meta" aria-live="polite">
                <span className="bb-item-pct">
                  {isConverting ? 'Encoding MP3…' : `${item.percent.toFixed(1)}%`}
                </span>
                <span className="bb-item-telemetry">
                  {displaySpeed && <span className="bb-speed">{displaySpeed}</span>}
                  {displaySpeed && displayEta && <span className="bb-dot-sep">•</span>}
                  {displayEta && <span className="bb-eta">ETA {displayEta}</span>}
                </span>
              </div>
            </div>
          )}

          {/* Error Message Display */}
          {isError && item.error && (
            <div className="bb-item-error-box">
              <AlertIcon size={14} className="bb-error-box-icon" />
              <span className="bb-error-box-msg">{item.error}</span>
            </div>
          )}
        </div>

        {/* Right column: Action buttons */}
        <div className="bb-item-action">
          {isDone && (
            <a
              href={downloadUrl}
              download
              className="bb-btn bb-btn-download-mp3"
              title="Download MP3 file"
            >
              <DownloadIcon size={15} />
              <span>Download MP3</span>
            </a>
          )}

          {isError && (
            <button
              type="button"
              className="bb-btn bb-btn-retry"
              onClick={handleRetry}
              disabled={isRetrying}
              title="Retry downloading this video"
            >
              {isRetrying ? (
                <>
                  <SpinnerIcon size={14} />
                  <span>Retrying…</span>
                </>
              ) : (
                <>
                  <RetryIcon size={14} />
                  <span>Retry</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
