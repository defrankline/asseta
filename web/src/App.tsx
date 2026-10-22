import { Box } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { BrowserRouter, useLocation, useNavigate } from 'react-router';
import { AuthProvider } from './auth/AuthProvider';
import { useAuth } from './auth/useAuth';
import { ErrorState } from './components/feedback/ErrorState';
import { LoadingState } from './components/feedback/LoadingState';
import {
  platformNotificationService,
  tenantNotificationService,
} from './api/services/notificationService';
import { PERMISSIONS } from './access/permissionCodes';
import { NotificationCenterProvider } from './notifications/center/NotificationCenterProvider';
import { NotificationProvider } from './notifications/NotificationProvider';
import { SessionRealtimeProvider } from './realtime/SessionRealtimeProvider';
import { LandingPage } from './pages/landing/LandingPage';
import { LoginRedirectPage } from './pages/LoginRedirectPage';
import { ROUTES } from './navigation/routes';
import { AppRoutes } from './routes/AppRoutes';
import { SessionProvider } from './session/SessionProvider';
import { useSession } from './session/useSession';
import { AppThemeProvider } from './theme/AppThemeProvider';

function SessionGate() {
  const { status, error, reload, mode, hasPermission } = useSession();
  if (status === 'loading') return <LoadingState label="Loading your access" />;
  if (status === 'error') {
    return (
      <Box className="p-6">
        <ErrorState error={error} title="Could not load your access" onRetry={reload} />
      </Box>
    );
  }
  const scopeKey = mode.kind === 'tenant' ? `tenant:${mode.tenantId}` : mode.kind;
  // One realtime connection per signed-in session, and the per-console notification inbox.
  return (
    <SessionRealtimeProvider>
      <NotificationCenterProvider
        service={mode.kind === 'tenant' ? tenantNotificationService : platformNotificationService}
        scopeKey={scopeKey}
        enabled={hasPermission(
          [PERMISSIONS.tenantNotificationRead, PERMISSIONS.platformNotificationRead],
          'any',
        )}
      >
        <AppRoutes />
      </NotificationCenterProvider>
    </SessionRealtimeProvider>
  );
}

function AuthGate() {
  const { status, error } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  if (status === 'initializing') return <LoadingState label="Signing in" />;
  // Signed-out visitors to the site root see the public page; deep links go straight to sign-in.
  if (status === 'unauthenticated')
    return pathname === '/' ? <LandingPage /> : <LoginRedirectPage />;
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
