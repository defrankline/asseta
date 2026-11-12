import { Alert, Box, Button, Link, Paper, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { toApiError, type ApiError } from '../api/ApiError';
import { meService } from '../api/services/meService';
import { useAuth } from '../auth/useAuth';
import { ConfirmDialog } from '../components/forms/ConfirmDialog';
import { useIdempotencyKey } from '../hooks/useIdempotencyKey';
import { ROUTES } from '../navigation/routes';
import { useSession } from '../session/useSession';
import { accountDeletedPath } from '../auth/signedOut';

export const CONFIRM_WORD = 'DELETE';

export const DELETE_ACCOUNT_TEXT =
  'Your login is deleted for good. Your name and email are removed; your records stay with the company under an anonymous name. This cannot be undone.';

export const PLATFORM_ACCOUNT_TEXT = 'Platform accounts are removed by the platform owner.';

/**
 * Profile -> Delete my account (`POST /me/account-deletion`). Refused for the last owner of a company
 * (the server says which; owners who may close it get a link) and for platform staff. On success the
 * old tokens no longer work, so the app signs out to the sign-in page with a message.
 */
export function DeleteAccountSection() {
  const { logout } = useAuth();
  const { me, mode, setMode } = useSession();
  const navigate = useNavigate();
  const keyFor = useIdempotencyKey();
  const [typed, setTyped] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const closable = (me?.tenants ?? []).filter((t) =>
    t.permissions.includes(PERMISSIONS.tenantCompanyClose),
  );

  const remove = async () => {
    const body = { confirm: true, reason: null };
    try {
      await meService.deleteMyAccount(null, keyFor(body));
      logout(accountDeletedPath());
    } catch (e) {
      setError(toApiError(e));
    }
  };

  const openClose = (tenantId: string) => {
    const go = () => {
      void navigate(ROUTES.tenantCompanyClose);
    };
    if (mode.kind === 'tenant' && mode.tenantId === tenantId) go();
    else void setMode({ kind: 'tenant', tenantId }, { onSwitched: go });
  };

  return (
    <Paper variant="outlined" className="p-4">
      <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
        Delete my account
      </Typography>
      <Typography variant="body2" color="text.secondary" className="mt-1 mb-3">
        {DELETE_ACCOUNT_TEXT}
      </Typography>
      <Stack spacing={2} sx={{ maxWidth: 480 }}>
        <TextField
          size="small"
          label={`Type ${CONFIRM_WORD} to confirm`}
          value={typed}
          onChange={(e) => {
            setTyped(e.target.value);
            setError(null);
          }}
          autoComplete="off"
        />
        {error !== null && (
          <Alert severity="error" role="alert">
            {error.code === 'PLATFORM_ACCOUNT' ? PLATFORM_ACCOUNT_TEXT : error.message}
            {error.code === 'LAST_OWNER' && closable.length > 0 && (
              <Box component="span" className="mt-1 block">
                Hand over the owner role, or close the company:{' '}
                {closable.map((t, i) => (
                  <span key={t.tenant_id}>
                    {i > 0 ? ', ' : ''}
                    <Link
                      component="button"
                      type="button"
                      onClick={() => {
                        openClose(t.tenant_id);
                      }}
                    >
                      Close {t.name}
                    </Link>
                  </span>
                ))}
              </Box>
            )}
          </Alert>
        )}
        <Box>
          <Button
            variant="contained"
            color="error"
            disabled={typed.trim() !== CONFIRM_WORD}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Delete my account
          </Button>
        </Box>
      </Stack>
      {confirming && (
        <ConfirmDialog
          open
          destructive
          title="Delete your account?"
          message={DELETE_ACCOUNT_TEXT}
          confirmLabel="Delete my account"
          onConfirm={remove}
          onClose={() => {
            setConfirming(false);
          }}
        />
      )}
    </Paper>
  );
}
