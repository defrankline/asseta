import { Box, Toolbar } from '@mui/material';
import { useState } from 'react';
import { Outlet } from 'react-router';
import { AppHeader } from './AppHeader';
import { MandateBanner } from './MandateBanner';
import { ManagedServiceNotice } from './ManagedServiceNotice';
import { SideNav } from './SideNav';
import { TenantAccessBanner } from './TenantAccessBanner';

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <Box className="flex min-h-screen">
      <AppHeader
        onToggleNav={() => {
          setMobileOpen((o) => !o);
        }}
      />
      <SideNav
        mobileOpen={mobileOpen}
        onClose={() => {
          setMobileOpen(false);
        }}
      />
      <Box
        component="a"
        href="#main-content"
        className="sr-only focus:not-sr-only"
        sx={{
          '&:focus': {
            position: 'fixed',
            top: 8,
            left: 8,
            zIndex: (t) => t.zIndex.tooltip + 1,
            px: 2,
            py: 1,
            borderRadius: 1,
            bgcolor: 'background.paper',
            color: 'text.primary',
            outline: '2px solid',
            outlineColor: 'primary.main',
          },
        }}
      >
        Skip to main content
      </Box>
      <Box
        component="main"
        id="main-content"
        tabIndex={-1}
        className="min-w-0 flex-1 p-4 outline-none md:p-6"
      >
        <Toolbar />
        <MandateBanner />
        <TenantAccessBanner />
        <ManagedServiceNotice />
        <Outlet />
      </Box>
    </Box>
  );
}
