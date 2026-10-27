import React from 'react';
import { LogoWaveform, MoonIcon, SunIcon } from './Icons';

interface HeaderProps {
  backendHealth: 'ok' | 'checking' | 'unreachable';
  onCheckHealth?: () => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  children?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({
  backendHealth,
  onCheckHealth,
  theme,
  onToggleTheme,
  children,
}) => {
  return (
    <header className="bb-header" role="banner">
      <div className="bb-header-brand">
        <div className="bb-logo-wrap" aria-hidden="true">
          <LogoWaveform size={40} className="bb-logo-icon" />
          <div className="bb-logo-glow" />
        </div>
        <div className="bb-brand-text">
          <div className="bb-brand-row">
            <h1 className="bb-title">
              Beat<span className="bb-title-highlight">Batch</span>
            </h1>
            <span className="bb-version-badge">v0.1</span>
          </div>
          <p className="bb-tagline">Drop your links. Get your beats.</p>
        </div>
      </div>

      <div className="bb-header-actions">
        {children}

        {/* Dark / Light Theme Toggle */}
        <button
          type="button"
          className="bb-theme-toggle"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
        >
          {theme === 'dark' ? (
            <SunIcon size={18} className="bb-theme-sun" />
          ) : (
            <MoonIcon size={18} className="bb-theme-moon" />
          )}
        </button>

        {/* API Health Status */}
        <div className="bb-header-status">
          <button
            type="button"
            className={`bb-health-pill bb-health-${backendHealth}`}
            onClick={onCheckHealth}
            aria-label={`Backend server status: ${backendHealth}`}
            title={
              backendHealth === 'ok'
                ? 'Backend API connected and healthy (click to re-check)'
                : backendHealth === 'checking'
                ? 'Connecting to backend...'
                : 'Backend unreachable. Make sure FastAPI server is running on :8000.'
            }
          >
            <span className="bb-status-dot" aria-hidden="true" />
            <span className="bb-status-label">
              {backendHealth === 'ok'
                ? 'API Online'
                : backendHealth === 'checking'
                ? 'Connecting…'
                : 'API Offline'}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};
