import ContentCopy from '@mui/icons-material/ContentCopy';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import { useState } from 'react';

interface OneTimePasswordDialogProps {
  title: string;
  /** Who it is for, e.g. "Daudi Mollel (supervisor@…)". */
  person: string;
  password: string;
  onClose: () => void;
}

/** Shows a one-time password once, with Copy. The person sets their own password at the next sign-in. */
export function OneTimePasswordDialog({
  title,
  person,
  password,
  onClose,
}: OneTimePasswordDialogProps) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <DialogContentText>
            Give this one-time password to {person}. They sign in with their email and this
            password, then choose their own.
          </DialogContentText>
          <Typography
            component="p"
            aria-label="One-time password"
            sx={{
              fontFamily: 'monospace',
              fontSize: '1.15rem',
              p: 1.5,
              borderRadius: 1,
              bgcolor: 'action.hover',
              wordBreak: 'break-all',
            }}
          >
            {password}
          </Typography>
          <Alert severity="info">
            It is shown only now. If it is lost, reset the password again.
          </Alert>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button
          startIcon={<ContentCopy />}
          onClick={() => {
            void navigator.clipboard
              .writeText(password)
              .then(() => {
                setCopied(true);
              })
              .catch(() => undefined);
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button variant="contained" onClick={onClose}>
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}
