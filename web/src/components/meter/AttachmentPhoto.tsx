import { Alert, Box, Button, Dialog, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useState } from 'react';
import { toApiError } from '../../api/ApiError';
import type { PhotoUrlDto } from '../../api/types';

interface AttachmentPhotoProps {
  attachmentId: string;
  /** getAttachmentUrl: a short-lived signed URL, fetched only when the user asks to view. */
  fetchUrl: (attachmentId: string) => Promise<PhotoUrlDto>;
  label?: string;
}

type State =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'ready'; url: string; expiresIn: number }
  | { phase: 'error'; message: string };

/** Evidence image viewer: fetches a short-lived URL on demand and shows a thumbnail + full view. */
export function AttachmentPhoto({
  attachmentId,
  fetchUrl,
  label = 'View photo',
}: AttachmentPhotoProps) {
  const [state, setState] = useState<State>({ phase: 'idle' });
  const [open, setOpen] = useState(false);
  const load = async () => {
    setState({ phase: 'loading' });
    try {
      const r = await fetchUrl(attachmentId);
      setState({ phase: 'ready', url: r.url, expiresIn: r.expires_in_seconds });
    } catch (err) {
      setState({ phase: 'error', message: toApiError(err).message });
    }
  };
  if (state.phase !== 'ready') {
    return (
      <Box className="flex flex-col gap-1">
        <Button
          size="small"
          variant="outlined"
          loading={state.phase === 'loading'}
          onClick={() => {
            void load();
          }}
        >
          {label}
        </Button>
        {state.phase === 'error' && <Alert severity="error">{state.message}</Alert>}
      </Box>
    );
  }
  return (
    <Box className="flex flex-col items-start gap-1">
      <button
        type="button"
        className="cursor-zoom-in border-0 bg-transparent p-0"
        onClick={() => {
          setOpen(true);
        }}
        aria-label="Open full-size photo"
      >
        <img src={state.url} alt="Evidence thumbnail" className="h-24 w-32 rounded object-cover" />
      </button>
      <Typography variant="caption" color="text.secondary">
        Link valid for {state.expiresIn} s.{' '}
        <Button
          size="small"
          onClick={() => {
            void load();
          }}
        >
          Refresh link
        </Button>
      </Typography>
      <Dialog
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        maxWidth="lg"
      >
        <DialogTitle>Evidence photo</DialogTitle>
        <DialogContent>
          <img src={state.url} alt="Evidence" className="max-h-[80vh] max-w-full" />
        </DialogContent>
      </Dialog>
    </Box>
  );
}
