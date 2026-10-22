import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import {
  Collapse,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
} from '@mui/material';
import { useMemo, useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { activeGroupKey, buildNav, navItems } from '../navigation/buildNav';
import {
  loadNavGroupState,
  storeNavGroupState,
  type NavGroupState,
} from '../navigation/navGroupStorage';
import type { NavGroup } from '../navigation/routes';
import { useSession } from '../session/useSession';
import { navGroupIcon } from './navGroupIcons';

export const NAV_WIDTH = 248;

interface SideNavProps {
  mobileOpen: boolean;
  onClose: () => void;
}

function groupDomId(idPrefix: string, key: string): string {
  return `${idPrefix}-${key.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}

/**
 * Expanded state per group: the viewer's remembered choice, collapsed by default, and the group of
 * the active route always opened when the route enters it.
 */
function useGroupState(activeKey: string | null) {
  const [state, setState] = useState<NavGroupState>(() => {
    const stored = loadNavGroupState();
    return activeKey === null ? stored : { ...stored, [activeKey]: true };
  });
  const [seenActive, setSeenActive] = useState(activeKey);
  if (seenActive !== activeKey) {
    setSeenActive(activeKey);
    if (activeKey !== null && state[activeKey] !== true) {
      const next = { ...state, [activeKey]: true };
      setState(next);
      storeNavGroupState(next);
    }
  }
  const toggle = (key: string) => {
    const next = { ...state, [key]: state[key] !== true };
    setState(next);
    storeNavGroupState(next);
  };
  return { isOpen: (key: string) => state[key] === true, toggle };
}

interface NavGroupListProps {
  /** Distinguishes the mobile and desktop drawers' element ids. */
  idPrefix: string;
  groups: readonly NavGroup[];
  isOpen: (key: string) => boolean;
  onToggle: (key: string) => void;
  onNavigate: () => void;
}

function NavGroupList({ idPrefix, groups, isOpen, onToggle, onNavigate }: NavGroupListProps) {
  const paths = navItems(groups).map((i) => i.path);
  return (
    <List dense component="div">
      {groups.map((group) => {
        const open = isOpen(group.key);
        const regionId = groupDomId(idPrefix, group.key);
        const Icon = navGroupIcon(group.key);
        return (
          <div key={group.key}>
            <ListItemButton
              aria-expanded={open}
              aria-controls={regionId}
              onClick={() => {
                onToggle(group.key);
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText
                primary={group.label}
                slotProps={{ primary: { sx: { fontWeight: 600 } } }}
              />
              {open ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
            </ListItemButton>
            <Collapse in={open} timeout="auto" unmountOnExit>
              <List dense component="ul" id={regionId} aria-label={group.label} disablePadding>
                {group.items.map((item) => (
                  <li key={item.key}>
                    <ListItemButton
                      component={NavLink}
                      to={item.path}
                      // A parent path (e.g. /platform) must not stay active on its children's pages.
                      end={paths.some((p) => p !== item.path && p.startsWith(`${item.path}/`))}
                      onClick={onNavigate}
                      sx={{
                        pl: 6.5,
                        '&.active': { bgcolor: 'action.selected', fontWeight: 600 },
                      }}
                    >
                      <ListItemText primary={item.label} />
                    </ListItemButton>
                  </li>
                ))}
              </List>
            </Collapse>
          </div>
        );
      })}
    </List>
  );
}

export function SideNav({ mobileOpen, onClose }: SideNavProps) {
  const { me, mode, activeTenant } = useSession();
  const { pathname } = useLocation();
  const groups = useMemo(() => buildNav(mode, activeTenant, me), [mode, activeTenant, me]);
  const { isOpen, toggle } = useGroupState(activeGroupKey(groups, pathname));

  // Both drawers render the same list; the open/closed state lives here so they never disagree.
  const content = (idPrefix: string) => (
    <>
      <Toolbar />
      <nav aria-label="Main">
        <NavGroupList
          idPrefix={idPrefix}
          groups={groups}
          isOpen={isOpen}
          onToggle={toggle}
          onNavigate={onClose}
        />
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
        {content('nav-mobile')}
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{ display: { xs: 'none', md: 'block' }, width: NAV_WIDTH, flexShrink: 0, ...paper }}
      >
        {content('nav')}
      </Drawer>
    </>
  );
}
