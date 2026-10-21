import { Box, Button, Typography } from '@mui/material';
import { useEffect } from 'react';
import { useAuth } from '../auth/useAuth';
import { Logo } from '../layout/Logo';

/** Shown when unauthenticated: immediately redirects to Keycloak, with a manual fallback. */
export function LoginRedirectPage() {
  const { login } = useAuth();
  useEffect(() => {
    login();
  }, [login]);
  return (
    <Box className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
      <Logo height={48} />
      <Typography variant="body1">Redirecting to sign in…</Typography>
      <Button variant="contained" onClick={login}>
        Sign in
      </Button>
    </Box>
  );
}
