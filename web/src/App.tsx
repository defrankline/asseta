import { Box } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { BrowserRouter, useNavigate } from 'react-router';
import { AuthProvider } from './auth/AuthProvider';
import { useAuth } from './auth/useAuth';
import { ErrorState } from './components/feedback/ErrorState';
import { LoadingState } from './components/feedback/LoadingState';
import { NotificationProvider } from './notifications/NotificationProvider';
import { LoginRedirectPage } from './pages/LoginRedirectPage';
import { ROUTES } from './navigation/routes';
import { AppRoutes } from './routes/AppRoutes';
import { SessionProvider } from './session/SessionProvider';
import { useSession } from './session/useSession';
import { AppThemeProvider } from './theme/AppThemeProvider';

function SessionGate() {
  const { status, error, reload } = useSession();
  if (status === 'loading') return <LoadingState label="Loading your access" />;
  if (status === 'error') {
    return (
      <Box className="p-6">
        <ErrorState error={error} title="Could not load your access" onRetry={reload} />
      </Box>
    );
  }
  return <AppRoutes />;
}

function AuthGate() {
  const { status, error } = useAuth();
  const navigate = useNavigate();
  if (status === 'initializing') return <LoadingState label="Signing in" />;
  if (status === 'unauthenticated') return <LoginRedirectPage />;
  if (status === 'error') {
    return (
      <Box className="p-6">
        <ErrorState
          error={new Error(error ?? 'Identity provider unavailable.')}
          title="Sign-in unavailable"
          onRetry={() => {
            window.location.reload();
          }}
        />
      </Box>
    );
  }
  return (
    <SessionProvider
      onMandateLost={() => {
        void navigate(ROUTES.home, { replace: true });
      }}
    >
      <SessionGate />
    </SessionProvider>
  );
}

export function App() {
  return (
    <AppThemeProvider>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <NotificationProvider>
          <BrowserRouter>
            <AuthProvider>
              <AuthGate />
            </AuthProvider>
          </BrowserRouter>
        </NotificationProvider>
      </LocalizationProvider>
    </AppThemeProvider>
  );
}
