import { Alert, Box, Button, Typography } from '@mui/material';
import { useEffect, useRef, useState } from 'react';
import { toApiError } from '../../api/ApiError';
import type { AttachmentDto } from '../../api/types';

interface AttachmentUploadProps {
  label: string;
  value: AttachmentDto | null;
  onChange: (value: AttachmentDto | null) => void;
  /** Uploads the original file (uploadAttachment); the server stores it immutably with its hash. */
  upload: (file: File) => Promise<AttachmentDto>;
  accept?: string;
  required?: boolean;
  helperText?: string;
  disabled?: boolean;
  /** Opens the device camera on phones/tablets (`capture` attribute); laptops still get a file chooser. */
  capture?: 'environment' | 'user';
  /** Shows a local preview of the uploaded image (the stored original is what the server keeps). */
  preview?: boolean;
}

/** Object URL of a picked image for preview, revoked when replaced or unmounted. */
function usePreviewUrl(): [string | null, (file: File | null) => void] {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(
    () => () => {
      if (url !== null) URL.revokeObjectURL(url);
    },
    [url],
  );
  const set = (file: File | null) => {
    const canPreview =
      file !== null && file.type.startsWith('image/') && typeof URL.createObjectURL === 'function';
    setUrl(canPreview ? URL.createObjectURL(file) : null);
  };
  return [url, set];
}

/** File picker that uploads immediately and keeps the returned attachment reference. */
export function AttachmentUpload({
  label,
  value,
  onChange,
  upload,
  accept = 'image/*',
  required = false,
  helperText,
  disabled = false,
  capture,
  preview = false,
}: AttachmentUploadProps) {
  const input = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreview] = usePreviewUrl();
  const pick = async (file: File | undefined) => {
    if (file === undefined) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await upload(file));
      if (preview) setPreview(file);
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusy(false);
      if (input.current !== null) input.current.value = '';
    }
  };
  return (
    <Box className="flex flex-col gap-1">
      <Typography variant="body2">
        {label}
        {required ? ' *' : ''}
      </Typography>
      <Box className="flex flex-wrap items-center gap-2">
        <Button
          variant="outlined"
          size="small"
          loading={busy}
          disabled={disabled}
          onClick={() => input.current?.click()}
        >
          {value === null ? 'Choose file' : 'Replace file'}
        </Button>
        {value !== null && (
          <>
            <Typography variant="caption" className="font-mono">
              Uploaded · SHA-256 {value.sha256.slice(0, 12)}… · {value.size_bytes} bytes
            </Typography>
            <Button
              size="small"
              onClick={() => {
                onChange(null);
                setPreview(null);
              }}
            >
              Remove
            </Button>
          </>
        )}
        <input
          ref={input}
          type="file"
          hidden
          accept={accept}
          {...(capture !== undefined ? { capture } : {})}
          aria-label={label}
          onChange={(e) => {
            void pick(e.target.files?.[0]);
          }}
        />
      </Box>
      {preview && value !== null && previewUrl !== null && (
        <img
          src={previewUrl}
          alt={`${label} preview`}
          className="max-h-48 max-w-full self-start rounded object-contain"
        />
      )}
      {helperText !== undefined && (
        <Typography variant="caption" color="text.secondary">
          {helperText}
        </Typography>
      )}
      {error !== null && <Alert severity="error">{error}</Alert>}
    </Box>
  );
}
