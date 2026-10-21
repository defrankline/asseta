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
      <Box component="main" className="min-w-0 flex-1 p-4 md:p-6">
        <Toolbar />
        <MandateBanner />
        <TenantAccessBanner />
        <ManagedServiceNotice />
        <Outlet />
      </Box>
    </Box>
  );
}
