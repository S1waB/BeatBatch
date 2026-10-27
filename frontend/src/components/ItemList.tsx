import React, { useMemo, useState } from 'react';
import type { JobItem } from '../api/types';
import { ItemCard } from './ItemCard';
import { RetryIcon } from './Icons';

interface ItemListProps {
  items: JobItem[];
  jobId: string;
  onRetry: (index: number) => Promise<void>;
  onRetryAllFailed?: () => Promise<void>;
  isRetryingAll?: boolean;
}

type FilterTab = 'all' | 'active' | 'done' | 'error';

export const ItemList: React.FC<ItemListProps> = ({
  items,
  jobId,
  onRetry,
  onRetryAllFailed,
  isRetryingAll = false,
}) => {
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const counts = useMemo(() => {
    return {
      all: items.length,
      active: items.filter((i) => i.status === 'downloading' || i.status === 'converting' || i.status === 'queued').length,
      done: items.filter((i) => i.status === 'done').length,
      error: items.filter((i) => i.status === 'error').length,
    };
  }, [items]);

  const filteredItemsWithIndex = useMemo(() => {
    return items
      .map((item, originalIndex) => ({ item, originalIndex }))
      .filter(({ item }) => {
        // Tab filter
        if (activeTab === 'active') {
          if (!['downloading', 'converting', 'queued'].includes(item.status)) return false;
        } else if (activeTab === 'done') {
          if (item.status !== 'done') return false;
        } else if (activeTab === 'error') {
          if (item.status !== 'error') return false;
        }

        // Search query filter
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchTitle = item.title?.toLowerCase().includes(q);
          const matchUrl = item.url.toLowerCase().includes(q);
          const matchId = item.video_id.toLowerCase().includes(q);
          if (!matchTitle && !matchUrl && !matchId) return false;
        }

        return true;
      });
  }, [items, activeTab, searchQuery]);

  return (
    <section className="bb-items-section">
      <div className="bb-items-toolbar">
        <div className="bb-filter-tabs">
          <button
            type="button"
            className={`bb-tab ${activeTab === 'all' ? 'bb-tab-active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            All Tracks <span className="bb-tab-count">{counts.all}</span>
          </button>
          <button
            type="button"
            className={`bb-tab ${activeTab === 'active' ? 'bb-tab-active' : ''}`}
            onClick={() => setActiveTab('active')}
          >
            Active <span className="bb-tab-count">{counts.active}</span>
          </button>
          <button
            type="button"
            className={`bb-tab ${activeTab === 'done' ? 'bb-tab-active' : ''}`}
            onClick={() => setActiveTab('done')}
          >
            Completed <span className="bb-tab-count">{counts.done}</span>
          </button>
          {counts.error > 0 && (
            <button
              type="button"
              className={`bb-tab bb-tab-has-errors ${
                activeTab === 'error' ? 'bb-tab-active' : ''
              }`}
              onClick={() => setActiveTab('error')}
              aria-label={`Show ${counts.error} failed tracks`}
            >
              Errors <span className="bb-tab-count bb-tab-error-count">{counts.error}</span>
            </button>
          )}
        </div>

        <div className="bb-items-toolbar-right">
          {counts.error > 0 && onRetryAllFailed && (
            <button
              type="button"
              className="bb-btn-ghost bb-btn-retry-inline"
              onClick={onRetryAllFailed}
              disabled={isRetryingAll}
              title="Retry all failed downloads"
              aria-label="Retry all failed downloads"
            >
              <RetryIcon size={14} />
              <span>Retry All Failed ({counts.error})</span>
            </button>
          )}

          {items.length > 5 && (
            <div className="bb-search-box">
              <input
                type="text"
                className="bb-search-input"
                placeholder="Search tracks…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="bb-search-clear"
                  onClick={() => setSearchQuery('')}
                >
                  ×
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="bb-items-grid">
        {filteredItemsWithIndex.length === 0 ? (
          <div className="bb-empty-filter-state">
            <p>No tracks match the selected filter.</p>
          </div>
        ) : (
          filteredItemsWithIndex.map(({ item, originalIndex }) => (
            <ItemCard
              key={`${item.video_id}-${originalIndex}`}
              item={item}
              index={originalIndex}
              jobId={jobId}
              onRetry={onRetry}
            />
          ))
        )}
      </div>
    </section>
  );
};
