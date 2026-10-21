import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import Logout from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material';
import { useAuth } from '../auth/useAuth';
import { useSession } from '../session/useSession';
import { useColorMode } from '../theme/ColorModeContext';
import { ConsoleSwitcher } from './ConsoleSwitcher';
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
      <Toolbar className="gap-3">
        <IconButton
          color="inherit"
          edge="start"
          aria-label="Toggle navigation"
          onClick={onToggleNav}
          className="md:hidden"
        >
          <MenuIcon />
        </IconButton>
        <Logo height={30} />
        <Box className="flex-1" />
        <ConsoleSwitcher />
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
