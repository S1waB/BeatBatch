import React from 'react';
import { api } from '../api/client';
import type { JobStatus } from '../api/types';
import {
  CheckIcon,
  HistoryIcon,
  TrashIcon,
  ZipIcon,
} from './Icons';

export interface HistoryRecord {
  id: string;
  createdAt: string;
  quality: string;
  total: number;
  doneCount: number;
  status: JobStatus;
}

interface HistoryPanelProps {
  history: HistoryRecord[];
  activeJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onClearHistory: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const HistoryPanel: React.FC<HistoryPanelProps> = ({
  history,
  activeJobId,
  onSelectJob,
  onClearHistory,
  isOpen,
  onToggle,
}) => {
  return (
    <div className="bb-history-wrapper">
      <button
        type="button"
        className={`bb-history-toggle ${isOpen ? 'bb-history-toggle-active' : ''}`}
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls="session-history-drawer"
        title="Session Download History"
      >
        <HistoryIcon size={16} />
        <span>History ({history.length})</span>
      </button>

      {isOpen && (
        <div
          id="session-history-drawer"
          className="bb-history-drawer"
          role="region"
          aria-label="Session Download History"
        >
          <div className="bb-history-drawer-header">
            <div className="bb-history-drawer-title-wrap">
              <HistoryIcon size={16} />
              <h3 className="bb-history-drawer-title">Session History</h3>
            </div>
            {history.length > 0 && (
              <button
                type="button"
                className="bb-btn-ghost bb-btn-danger-ghost bb-history-clear-btn"
                onClick={onClearHistory}
                title="Clear history records"
              >
                <TrashIcon size={13} />
                <span>Clear</span>
              </button>
            )}
          </div>

          <p className="bb-history-retention-note">
            💡 Downloaded files are retained on the server for 24 hours.
          </p>

          {history.length === 0 ? (
            <div className="bb-history-empty">
              <p>No downloads yet in this session.</p>
            </div>
          ) : (
            <ul className="bb-history-list">
              {history.map((record) => {
                const isSelected = activeJobId === record.id;
                const dateObj = new Date(record.createdAt);
                const timeString = isNaN(dateObj.getTime())
                  ? 'Just now'
                  : dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                const zipUrl = api.getZipDownloadUrl(record.id);

                return (
                  <li
                    key={record.id}
                    className={`bb-history-item ${isSelected ? 'bb-history-item-selected' : ''}`}
                  >
                    <div className="bb-history-item-info">
                      <div className="bb-history-item-top">
                        <span className={`bb-status-pill bb-status-${record.status}`}>
                          {record.status.toUpperCase()}
                        </span>
                        <span className="bb-history-quality">{record.quality} kbps</span>
                        <span className="bb-history-time">{timeString}</span>
                      </div>
                      <div className="bb-history-item-meta">
                        <span>
                          <CheckIcon size={12} className="inline-check" />
                          <strong>{record.doneCount}</strong> / {record.total} tracks
                        </span>
                      </div>
                    </div>

                    <div className="bb-history-item-actions">
                      <button
                        type="button"
                        className="bb-btn-ghost bb-btn-history-view"
                        onClick={() => onSelectJob(record.id)}
                        disabled={isSelected}
                      >
                        {isSelected ? 'Viewing' : 'View'}
                      </button>

                      {record.doneCount > 0 && (
                        <a
                          href={zipUrl}
                          download
                          className="bb-btn-ghost bb-btn-history-zip"
                          title="Download ZIP"
                        >
                          <ZipIcon size={13} />
                          <span>ZIP</span>
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
