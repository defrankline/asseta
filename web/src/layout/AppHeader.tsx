import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import Logout from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material';
import { useAuth } from '../auth/useAuth';
import { NotificationBell } from '../notifications/center/NotificationBell';
import { ConnectionIndicator } from '../realtime/ConnectionIndicator';
import { useSession } from '../session/useSession';
import { useColorMode } from '../theme/ColorModeContext';
import { TenantSwitcher } from './TenantSwitcher';
import { Logo } from './Logo';

interface AppHeaderProps {
  onToggleNav: () => void;
}

export function AppHeader({ onToggleNav }: AppHeaderProps) {
  const { logout } = useAuth();
  const { me } = useSession();
  const { mode, toggle } = useColorMode();

  return (
    <AppBar position="fixed" elevation={0} sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
      <Toolbar className="gap-1 sm:gap-3">
        <IconButton
          color="inherit"
          edge="start"
          aria-label="Toggle navigation"
          onClick={onToggleNav}
          className="md:hidden"
        >
          <MenuIcon />
        </IconButton>
        <Box className="hidden shrink-0 sm:block">
          <Logo height={30} />
        </Box>
        <Box className="shrink-0 sm:hidden">
          <Logo height={24} compact />
        </Box>
        <Box className="flex-1" />
        <TenantSwitcher />
        <ConnectionIndicator />
        <NotificationBell />
        {me !== null && (
          <Typography variant="body2" className="hidden sm:block">
            {me.display_name}
          </Typography>
        )}
        <Tooltip title={mode === 'light' ? 'Dark mode' : 'Light mode'}>
          <IconButton color="inherit" aria-label="Toggle colour mode" onClick={toggle}>
            {mode === 'light' ? <DarkModeOutlined /> : <LightModeOutlined />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Sign out">
          <IconButton color="inherit" aria-label="Sign out" onClick={logout}>
            <Logout />
          </IconButton>
        </Tooltip>
      </Toolbar>
    </AppBar>
  );
}
