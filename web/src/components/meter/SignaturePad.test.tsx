import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AttachmentDto } from '../../api/types';
import { SignaturePad } from './SignaturePad';

const ATTACHMENT: AttachmentDto = {
  id: 'att-1',
  sha256: 'abcdef0123456789abcdef',
  content_type: 'image/png',
  size_bytes: 1234,
  purpose: 'SIGNATURE',
  uploaded_at: '2026-10-21T16:00:00Z',
};

const ctx = {
  fillRect: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  stroke: vi.fn(),
};

beforeEach(() => {
  // jsdom has no canvas: stub the 2D context, PNG export and pointer capture.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => {
    cb(new Blob(['png'], { type: 'image/png' }));
  });
  HTMLCanvasElement.prototype.setPointerCapture = vi.fn();
});
afterEach(() => {
  vi.restoreAllMocks();
});

function Harness({ upload }: { upload: (f: File) => Promise<AttachmentDto> }) {
  const [value, setValue] = useState<AttachmentDto | null>(null);
  return (
    <SignaturePad label="Customer signature" value={value} onChange={setValue} upload={upload} />
  );
}

describe('SignaturePad', () => {
  it('uploads the drawn signature as a PNG only after something is drawn', async () => {
    const user = userEvent.setup();
    const upload = vi.fn<(f: File) => Promise<AttachmentDto>>(() => Promise.resolve(ATTACHMENT));
    render(<Harness upload={upload} />);
    const save = screen.getByRole('button', { name: 'Use this signature' });
    expect(save).toBeDisabled();
    const pad = screen.getByRole('img', { name: 'Customer signature drawing area' });
    fireEvent.pointerDown(pad, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(pad, { clientX: 40, clientY: 20, pointerId: 1 });
    fireEvent.pointerUp(pad, { pointerId: 1 });
    expect(ctx.stroke).toHaveBeenCalled();
    await user.click(save);
    await waitFor(() => {
      expect(upload).toHaveBeenCalledTimes(1);
    });
    const file = upload.mock.calls[0]?.[0];
    expect(file?.name).toBe('signature.png');
    expect(file?.type).toBe('image/png');
    expect(await screen.findByText(/Signature saved · SHA-256 abcdef012345/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear' }));
    expect(screen.getByRole('button', { name: 'Use this signature' })).toBeDisabled();
  });
});
