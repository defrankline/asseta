import { Alert, Box, Button, Typography } from '@mui/material';
import { useEffect } from 'react';
import { useLocation } from 'react-router';
import { useAuth } from '../auth/useAuth';
import { Logo } from '../layout/Logo';
import { ROUTES } from '../navigation/routes';
import { SIGNED_OUT_REASON } from '../auth/signedOut';

/**
 * Shown when unauthenticated: immediately redirects to Keycloak, with a manual fallback. After the
 * app signed the person out with a reason (e.g. their account was deleted) it shows that message and
 * waits for them instead of redirecting.
 */
export function LoginRedirectPage() {
  const { login } = useAuth();
  const { pathname, search } = useLocation();
  const accountDeleted =
    pathname === ROUTES.signedOut &&
    new URLSearchParams(search).get('reason') === SIGNED_OUT_REASON.accountDeleted;
  useEffect(() => {
    if (!accountDeleted) login();
  }, [login, accountDeleted]);
  return (
    <Box className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
      <Logo height={48} />
      {accountDeleted ? (
        <Alert severity="success" role="status" sx={{ maxWidth: 480 }}>
          Your account was deleted and you are signed out. Your records stay with each company under
          an anonymous name.
        </Alert>
      ) : (
        <Typography variant="body1">Redirecting to sign in…</Typography>
      )}
      <Button variant="contained" onClick={login}>
        Sign in
      </Button>
    </Box>
  );
}
