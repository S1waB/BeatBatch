import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Quality, ValidateResponse } from '../api/types';
import { useDebounce } from '../hooks/useDebounce';
import {
  AlertIcon,
  CheckIcon,
  FileTextIcon,
  PlayIcon,
  SpinnerIcon,
  TrashIcon,
  UploadIcon,
} from './Icons';
import { useToast } from '../hooks/useToast';

interface LinkInputProps {
  onStartJob: (text: string, quality: Quality) => Promise<void>;
  isStarting: boolean;
  disabled?: boolean;
}

const SAMPLE_TEXT = `# BeatBatch Sample Links (one per line)
https://www.youtube.com/watch?v=jfKfPfyJRdk
https://youtu.be/dQw4w9WgXcY
https://www.youtube.com/watch?v=9bZkp7q19f0
`;

const QUALITIES: { value: Quality; label: string; desc: string }[] = [
  { value: '128', label: '128 kbps', desc: 'Compact / Fast' },
  { value: '192', label: '192 kbps', desc: 'Recommended' },
  { value: '256', label: '256 kbps', desc: 'High Quality' },
  { value: '320', label: '320 kbps', desc: 'Max Fidelity' },
];

export const LinkInput: React.FC<LinkInputProps> = ({
  onStartJob,
  isStarting,
  disabled = false,
}) => {
  const { showToast } = useToast();

  // Load persisted draft and quality from localStorage
  const [text, setText] = useState<string>(() => {
    return localStorage.getItem('beatbatch_draft') || '';
  });

  const [quality, setQuality] = useState<Quality>(() => {
    const saved = localStorage.getItem('beatbatch_quality');
    if (saved === '128' || saved === '192' || saved === '256' || saved === '320') {
      return saved;
    }
    return '192';
  });

  const [validation, setValidation] = useState<ValidateResponse | null>(null);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [showInvalidDetails, setShowInvalidDetails] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debouncedText = useDebounce(text, 350);

  // Persist draft in localStorage
  useEffect(() => {
    localStorage.setItem('beatbatch_draft', text);
  }, [text]);

  // Persist quality in localStorage
  useEffect(() => {
    localStorage.setItem('beatbatch_quality', quality);
  }, [quality]);

  // Validate whenever debounced text changes
  useEffect(() => {
    const trimmed = debouncedText.trim();
    if (!trimmed) {
      return;
    }

    let isMounted = true;
    const timer = setTimeout(() => {
      setIsValidating(true);
      api
        .validateLinks(debouncedText)
        .then((res) => {
          if (isMounted) {
            setValidation(res);
            setIsValidating(false);
          }
        })
        .catch(() => {
          if (isMounted) {
            setIsValidating(false);
          }
        });
    }, 0);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [debouncedText]);

  const handleStart = async () => {
    if (!validation || validation.total_valid === 0 || isStarting || disabled) {
      return;
    }
    await onStartJob(text, quality);
  };

  const handleLoadSample = () => {
    setText(SAMPLE_TEXT);
    showToast('info', 'Sample links loaded');
  };

  const handleClear = () => {
    setText('');
    setValidation(null);
    setShowInvalidDetails(false);
    localStorage.removeItem('beatbatch_draft');
  };

  // Keyboard shortcut Ctrl+Enter or Cmd+Enter to start
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (validation && validation.total_valid > 0 && !isStarting && !disabled) {
        handleStart();
      }
    }
  };

  // Process dropped or imported file
  const processImportFile = async (file: File) => {
    if (!file.name.endsWith('.txt') && file.type !== 'text/plain') {
      showToast('error', 'Invalid file type', 'Please drop a .txt text file containing YouTube links.');
      return;
    }

    try {
      const content = await file.text();
      if (!content.trim()) {
        showToast('info', 'File was empty', `${file.name} did not contain any text.`);
        return;
      }

      setText((prev) => {
        const separator = prev.trim() ? '\n' : '';
        return `${prev.trim()}${separator}${content}`;
      });

      showToast('success', 'Links imported', `Imported links from ${file.name}`);
      textareaRef.current?.focus();
    } catch {
      showToast('error', 'Import failed', `Failed to read ${file.name}`);
    }
  };

  // Drag and drop events
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only unset if leaving the drop container
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await processImportFile(file);
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processImportFile(e.target.files[0]);
      e.target.value = '';
    }
  };

  const totalValid = validation?.total_valid ?? 0;
  const totalInvalid = validation?.total_invalid ?? 0;
  const hasText = text.trim().length > 0;
  const canStart = totalValid > 0 && !isStarting && !disabled;

  return (
    <section className="bb-input-panel" aria-labelledby="input-section-title">
      <div className="bb-input-header">
        <div className="bb-input-heading-wrap">
          <h2 id="input-section-title" className="bb-input-heading">
            Add YouTube Links
          </h2>
          <span className="bb-input-subheading">
            One link per line • Drop a <code>.txt</code> file • Press <kbd>Ctrl+↵</kbd> to start
          </span>
        </div>

        <div className="bb-input-quick-actions">
          {/* File input for manual upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,text/plain"
            style={{ display: 'none' }}
            onChange={handleFileInputChange}
          />

          <button
            type="button"
            className="bb-btn-ghost"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isStarting}
            title="Import links from a .txt file"
            aria-label="Import links from text file"
          >
            <FileTextIcon size={14} />
            <span>Import .txt</span>
          </button>

          {!hasText && (
            <button
              type="button"
              className="bb-btn-ghost"
              onClick={handleLoadSample}
              disabled={disabled || isStarting}
              aria-label="Paste sample links"
            >
              Paste Sample Links
            </button>
          )}

          {hasText && (
            <button
              type="button"
              className="bb-btn-ghost bb-btn-danger-ghost"
              onClick={handleClear}
              disabled={disabled || isStarting}
              title="Clear all links and draft"
              aria-label="Clear all links"
            >
              <TrashIcon size={14} />
              <span>Clear</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Textarea with Drag & Drop */}
      <div
        className={`bb-textarea-container ${isDragging ? 'bb-textarea-dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="bb-drop-overlay" aria-hidden="true">
            <UploadIcon size={36} className="bb-drop-icon" />
            <strong className="bb-drop-text">Drop .txt file to import links</strong>
          </div>
        )}

        <textarea
          ref={textareaRef}
          id="youtube-links-input"
          className="bb-textarea"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (!e.target.value.trim()) {
              setValidation(null);
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={`Paste YouTube links here, one per line (or drag & drop a .txt file):\nhttps://www.youtube.com/watch?v=...\nhttps://youtu.be/...\nhttps://www.youtube.com/shorts/...`}
          rows={7}
          disabled={disabled || isStarting}
          spellCheck={false}
          autoComplete="off"
          aria-label="YouTube video URLs, one per line"
          aria-describedby="counter-summary"
        />

        {/* Live Validation Bar */}
        <div className="bb-counter-bar" id="counter-summary" aria-live="polite">
          <div className="bb-counter-chips">
            {isValidating && (
              <span className="bb-chip bb-chip-validating" role="status">
                <SpinnerIcon size={13} />
                <span>Validating…</span>
              </span>
            )}

            {!isValidating && hasText && (
              <>
                <span
                  className={`bb-chip ${
                    totalValid > 0 ? 'bb-chip-success' : 'bb-chip-neutral'
                  }`}
                  role="status"
                >
                  <CheckIcon size={14} />
                  <span>
                    <strong>{totalValid}</strong> {totalValid === 1 ? 'valid link' : 'valid links'}
                  </span>
                </span>

                {totalInvalid > 0 && (
                  <button
                    type="button"
                    className="bb-chip bb-chip-warning bb-chip-clickable"
                    onClick={() => setShowInvalidDetails((prev) => !prev)}
                    title="Click to view invalid lines"
                    aria-expanded={showInvalidDetails}
                  >
                    <AlertIcon size={14} />
                    <span>
                      <strong>{totalInvalid}</strong> invalid
                    </span>
                    <span className="bb-chip-toggle">
                      {showInvalidDetails ? 'Hide' : 'Details'}
                    </span>
                  </button>
                )}
              </>
            )}

            {!hasText && (
              <span className="bb-chip bb-chip-hint">
                Lines starting with # will be treated as comments
              </span>
            )}
          </div>

          <div className="bb-char-counter">
            {text.split('\n').filter((l) => l.trim().length > 0).length} lines entered
          </div>
        </div>
      </div>

      {/* Invalid lines detail list */}
      {showInvalidDetails && validation && validation.invalid_lines.length > 0 && (
        <div className="bb-invalid-drawer" role="alert" aria-label="Invalid lines list">
          <div className="bb-invalid-drawer-title">
            <AlertIcon size={14} />
            <span>Lines requiring attention:</span>
          </div>
          <ul className="bb-invalid-list">
            {validation.invalid_lines.map((inv) => (
              <li key={`${inv.line_number}-${inv.text}`} className="bb-invalid-item">
                <span className="bb-line-tag">Line {inv.line_number}</span>
                <code className="bb-invalid-snippet">{inv.text || '(empty)'}</code>
                <span className="bb-invalid-reason">{inv.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Controls Bar: Quality Selector & Start Button */}
      <div className="bb-controls-bar">
        <div className="bb-quality-section" role="group" aria-label="Select audio quality">
          <label className="bb-controls-label" id="quality-label">
            Audio Bitrate
          </label>
          <div className="bb-quality-pills" role="radiogroup" aria-labelledby="quality-label">
            {QUALITIES.map((q) => {
              const isSelected = quality === q.value;
              return (
                <button
                  key={q.value}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`bb-quality-pill ${isSelected ? 'bb-quality-active' : ''}`}
                  onClick={() => setQuality(q.value)}
                  disabled={disabled || isStarting}
                >
                  <span className="bb-quality-val">{q.label}</span>
                  <span className="bb-quality-desc">{q.desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="bb-start-section">
          <button
            type="button"
            id="start-download-btn"
            className="bb-btn bb-btn-primary"
            onClick={handleStart}
            disabled={!canStart}
            title={canStart ? 'Start download batch (Ctrl+Enter)' : 'Enter valid links to start'}
            aria-label={`Start download batch for ${totalValid} links`}
          >
            {isStarting ? (
              <>
                <SpinnerIcon size={16} />
                <span>Starting Batch…</span>
              </>
            ) : (
              <>
                <PlayIcon size={16} />
                <span>Start Download ({totalValid})</span>
                <kbd className="bb-btn-kbd">Ctrl+↵</kbd>
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
};
