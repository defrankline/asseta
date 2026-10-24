import { Alert, Box, Button, Typography } from '@mui/material';
import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { toApiError } from '../../api/ApiError';
import type { AttachmentDto } from '../../api/types';
import { canvasPoint, PAD_HEIGHT, PAD_WIDTH } from './signature';

function blank(ctx: CanvasRenderingContext2D) {
  // White background so the stored PNG reads the same in any viewer.
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, PAD_WIDTH, PAD_HEIGHT);
  ctx.strokeStyle = '#111111';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
}

interface SignaturePadProps {
  label: string;
  value: AttachmentDto | null;
  onChange: (value: AttachmentDto | null) => void;
  /** Uploads the drawn signature (PNG) as evidence; the server stores it immutably with its hash. */
  upload: (file: File) => Promise<AttachmentDto>;
}

/** On-screen signature (mouse, pen or touch) saved as a PNG attachment. */
export function SignaturePad({ label, value, onChange, upload }: SignaturePadProps) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const [inked, setInked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ctx = () => canvas.current?.getContext('2d') ?? null;

  useEffect(() => {
    const c = ctx();
    if (c !== null) blank(c);
  }, []);

  const point = (e: PointerEvent<HTMLCanvasElement>) =>
    canvasPoint(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect());

  const clear = () => {
    const c = ctx();
    if (c !== null) blank(c);
    setInked(false);
    onChange(null);
  };

  const save = () => {
    setBusy(true);
    setError(null);
    canvas.current?.toBlob((blob) => {
      if (blob === null) {
        setBusy(false);
        setError('The signature could not be read from the drawing area.');
        return;
      }
      upload(new File([blob], 'signature.png', { type: 'image/png' }))
        .then(onChange)
        .catch((err: unknown) => {
          setError(toApiError(err).message);
        })
        .finally(() => {
          setBusy(false);
        });
    }, 'image/png');
  };

  return (
    <Box className="flex flex-col gap-1">
      <Typography variant="body2">{label} *</Typography>
      <canvas
        ref={canvas}
        width={PAD_WIDTH}
        height={PAD_HEIGHT}
        aria-label={`${label} drawing area`}
        role="img"
        className="w-full rounded border border-solid border-gray-400 bg-white"
        style={{ touchAction: 'none', aspectRatio: `${String(PAD_WIDTH)} / ${String(PAD_HEIGHT)}` }}
        onPointerDown={(e) => {
          if (value !== null) return; // saved: clear first to sign again
          const c = ctx();
          if (c === null) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          drawing.current = true;
          const p = point(e);
          c.beginPath();
          c.moveTo(p.x, p.y);
        }}
        onPointerMove={(e) => {
          const c = ctx();
          if (!drawing.current || c === null) return;
          const p = point(e);
          c.lineTo(p.x, p.y);
          c.stroke();
          setInked(true);
        }}
        onPointerUp={() => {
          drawing.current = false;
        }}
        onPointerLeave={() => {
          drawing.current = false;
        }}
      />
      <Box className="flex flex-wrap items-center gap-2">
        <Button size="small" onClick={clear} disabled={busy}>
          Clear
        </Button>
        {value === null ? (
          <Button size="small" variant="outlined" loading={busy} disabled={!inked} onClick={save}>
            Use this signature
          </Button>
        ) : (
          <Typography variant="caption" className="font-mono">
            Signature saved · SHA-256 {value.sha256.slice(0, 12)}…
          </Typography>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary">
        The customer representative signs here with a mouse, pen or finger.
      </Typography>
      {error !== null && <Alert severity="error">{error}</Alert>}
    </Box>
  );
}
