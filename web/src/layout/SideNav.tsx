import { Drawer, List, ListItemButton, ListItemText, Toolbar } from '@mui/material';
import { useMemo } from 'react';
import { NavLink } from 'react-router';
import { buildNav } from '../navigation/buildNav';
import { useSession } from '../session/useSession';

export const NAV_WIDTH = 248;

interface SideNavProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export function SideNav({ mobileOpen, onClose }: SideNavProps) {
  const { me, mode, activeTenant, permissions } = useSession();
  const items = useMemo(
    () => buildNav(mode, activeTenant, permissions, me),
    [mode, activeTenant, permissions, me],
  );

  const content = (
    <>
      <Toolbar />
      <nav aria-label="Main">
        <List dense>
          {items.map((item) => (
            <ListItemButton
              key={item.key}
              component={NavLink}
              to={item.path}
              // A parent path (e.g. /platform) must not stay active on its children's pages.
              end={items.some((o) => o.path !== item.path && o.path.startsWith(`${item.path}/`))}
              onClick={onClose}
              sx={{ '&.active': { bgcolor: 'action.selected', fontWeight: 600 } }}
            >
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </nav>
    </>
  );

  const paper = { '& .MuiDrawer-paper': { width: NAV_WIDTH, boxSizing: 'border-box' } } as const;
  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        sx={{ display: { xs: 'block', md: 'none' }, ...paper }}
      >
        {content}
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{ display: { xs: 'none', md: 'block' }, width: NAV_WIDTH, flexShrink: 0, ...paper }}
      >
        {content}
      </Drawer>
    </>
  );
}
