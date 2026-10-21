import WarningAmber from '@mui/icons-material/WarningAmber';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import type { OnboardResultDto } from '../../../api/types';
import { CopyButton } from '../../../components/display/CopyButton';

/** The idempotency replay of an onboarding never returns the real password. */
const REDACTED_PREFIX = '<redacted';

interface TemporaryPasswordDialogProps {
  result: OnboardResultDto;
  onClose: () => void;
}

/** Shows the owner's one-time temporary password exactly once after onboarding. */
export function TemporaryPasswordDialog({ result, onClose }: TemporaryPasswordDialogProps) {
  const password = result.owner_temporary_password;
  const redacted = password.startsWith(REDACTED_PREFIX);
  return (
    <Dialog open fullWidth maxWidth="sm" aria-labelledby="temp-password-title">
      <DialogTitle id="temp-password-title">Tenant onboarded</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Typography variant="body2">
            <strong>{result.tenant.display_name}</strong> was created. Share the temporary password
            with the owner <strong>{result.owner_email}</strong> through a secure channel; they must
            change it at first login.
          </Typography>
          {redacted ? (
            <Alert severity="warning">
              This onboarding was already completed and its password was shown earlier. It cannot be
              displayed again; reset the owner&apos;s password in the identity provider if needed.
            </Alert>
          ) : (
            <>
              <Alert severity="warning" icon={<WarningAmber />}>
                <AlertTitle>Shown once</AlertTitle>
                This password is not stored and will not be shown again after you close this dialog.
              </Alert>
              <Box className="flex flex-wrap items-center gap-3">
                <Box
                  component="code"
                  aria-label="Temporary password"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '1.1rem',
                    px: 1.5,
                    py: 1,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    userSelect: 'all',
                  }}
                >
                  {password}
                </Box>
                <CopyButton value={password} label="Copy password" />
              </Box>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={onClose}>
          I have saved it
        </Button>
      </DialogActions>
    </Dialog>
  );
}
