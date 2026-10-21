import { Alert, Box, Button, Typography } from '@mui/material';
import { useRef, useState } from 'react';
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
}: AttachmentUploadProps) {
  const input = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pick = async (file: File | undefined) => {
    if (file === undefined) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await upload(file));
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
          aria-label={label}
          onChange={(e) => {
            void pick(e.target.files?.[0]);
          }}
        />
      </Box>
      {helperText !== undefined && (
        <Typography variant="caption" color="text.secondary">
          {helperText}
        </Typography>
      )}
      {error !== null && <Alert severity="error">{error}</Alert>}
    </Box>
  );
}
