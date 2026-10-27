import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { LinkInput } from '../components/LinkInput';
import { ToastProvider } from '../components/ToastProvider';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    validateLinks: vi.fn(),
  },
}));

function renderLinkInput(props = {}) {
  const defaultProps = {
    onStartJob: vi.fn(),
    isStarting: false,
    disabled: false,
    ...props,
  };

  return render(
    <ToastProvider>
      <LinkInput {...defaultProps} />
    </ToastProvider>
  );
}

describe('LinkInput Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders textarea with placeholder and controls', () => {
    renderLinkInput();
    const textarea = screen.getByLabelText(/YouTube video URLs/i);
    expect(textarea).toBeInTheDocument();
    expect(screen.getByText(/Audio Bitrate/i)).toBeInTheDocument();
    expect(screen.getByText(/192 kbps/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Start download batch/i })).toBeDisabled();
  });

  it('displays live validation counter when valid links are typed', async () => {
    vi.mocked(api.validateLinks).mockResolvedValueOnce({
      valid_links: [
        {
          video_id: 'dQw4w9WgXcY',
          canonical_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcY',
          original_url: 'https://youtu.be/dQw4w9WgXcY',
        },
      ],
      invalid_lines: [],
      total_valid: 1,
      total_invalid: 0,
    });

    renderLinkInput();
    const textarea = screen.getByLabelText(/YouTube video URLs/i);
    fireEvent.change(textarea, { target: { value: 'https://youtu.be/dQw4w9WgXcY' } });

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/1\s+valid link/i);
    });

    const startBtn = screen.getByRole('button', { name: /Start download batch for 1 links/i });
    expect(startBtn).not.toBeDisabled();
  });

  it('allows selecting audio quality bitrate', () => {
    renderLinkInput();
    const pill320 = screen.getByText('320 kbps').closest('button');
    expect(pill320).toBeInTheDocument();
    fireEvent.click(pill320!);
    expect(pill320).toHaveClass('bb-quality-active');
  });

  it('displays invalid lines count when lines fail validation', async () => {
    vi.mocked(api.validateLinks).mockResolvedValueOnce({
      valid_links: [],
      invalid_lines: [
        {
          line_number: 1,
          text: 'not-a-link',
          reason: 'Unrecognized URL pattern',
        },
      ],
      total_valid: 0,
      total_invalid: 1,
    });

    renderLinkInput();
    const textarea = screen.getByLabelText(/YouTube video URLs/i);
    fireEvent.change(textarea, { target: { value: 'not-a-link' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /1\s+invalid/i })).toBeInTheDocument();
    });
  });
});
