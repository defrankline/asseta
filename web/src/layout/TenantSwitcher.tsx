import ExpandMore from '@mui/icons-material/ExpandMore';
import SwapHoriz from '@mui/icons-material/SwapHoriz';
import { Box, Button, ListItemText, Menu, MenuItem, TextField } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { TenantAccess } from '../api/types';
import { ROUTES } from '../navigation/routes';
import { mandateScopeLabel } from '../session/mandateDisplay';
import { serializeMode, type ConsoleMode } from '../session/permissions';
import { useSession } from '../session/useSession';

/** Above this many contexts the menu gets a search box (mandated clients can grow). */
export const SWITCHER_SEARCH_THRESHOLD = 8;

interface SwitchOption {
  mode: ConsoleMode;
  primary: string;
  secondary: string | null;
}

function tenantSecondary(t: TenantAccess): string | null {
  if (t.mandate !== undefined && t.mandate !== null) {
    return `${t.mandate.reference} · ${mandateScopeLabel(t.mandate.scope)}`;
  }
  return t.access_state !== 'FULL' ? t.access_state.replace('_', ' ').toLowerCase() : null;
}

/**
 * Header "Switch tenant" navigation menu (not a form dropdown). Platform staff see the platform
 * console ("Asseta platform", which is not a tenant) first, then each client they may act for
 * under an in-force mandate (from /me only).
 */
export function TenantSwitcher() {
  const { me, mode, activeTenant, canUsePlatform, setMode } = useSession();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [search, setSearch] = useState('');
  if (me === null) return null;

  const options: SwitchOption[] = [
    ...(canUsePlatform
      ? [
          {
            mode: { kind: 'platform' } as const,
            primary: 'Asseta platform',
            secondary: 'Platform console',
          },
        ]
      : []),
    ...me.tenants.map((t) => ({
      mode: { kind: 'tenant', tenantId: t.tenant_id } as const,
      primary: t.name,
      secondary: tenantSecondary(t),
    })),
  ];
  if (options.length === 0) return null;

  const current = mode.kind === 'none' ? '' : serializeMode(mode);
  const label =
    mode.kind === 'platform' ? 'Asseta platform' : (activeTenant?.name ?? 'Select a tenant');

  const searchable = options.length > SWITCHER_SEARCH_THRESHOLD;
  const needle = search.trim().toLocaleLowerCase();
  const shown =
    searchable && needle !== ''
      ? options.filter((o) =>
          `${o.primary} ${o.secondary ?? ''}`.toLocaleLowerCase().includes(needle),
        )
      : options;

  const close = () => {
    setAnchor(null);
    setSearch('');
  };
  const choose = async (next: ConsoleMode) => {
    close();
    if (serializeMode(next) === current) return;
    // Navigate home in the same update as the switch: never render the new console on the old
    // console's route (its permission guard would land on 403).
    await setMode(next, {
      onSwitched: () => {
        void navigate(ROUTES.home);
      },
    });
  };

  return (
    <>
      <Button
        color="inherit"
        aria-label={`Switch tenant (current: ${label})`}
        aria-haspopup="menu"
        aria-controls={anchor !== null ? 'tenant-switch-menu' : undefined}
        aria-expanded={anchor !== null}
        startIcon={<SwapHoriz />}
        endIcon={<ExpandMore />}
        onClick={(e) => {
          setAnchor(e.currentTarget);
        }}
        sx={{
          textTransform: 'none',
          bgcolor: 'rgba(255,255,255,0.08)',
          maxWidth: { xs: 132, sm: 320 },
          minWidth: 0,
          '& .MuiButton-startIcon': { display: { xs: 'none', sm: 'inherit' } },
        }}
      >
        <span className="truncate">{label}</span>
      </Button>
      <Menu id="tenant-switch-menu" anchorEl={anchor} open={anchor !== null} onClose={close}>
        {searchable && (
          <Box
            className="px-3 pb-2"
            onKeyDown={(e) => {
              // Keep typing in the box (the menu would otherwise jump to matching items).
              if (e.key !== 'Escape') e.stopPropagation();
            }}
          >
            <TextField
              size="small"
              fullWidth
              autoFocus
              placeholder="Search clients"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
              }}
              slotProps={{ htmlInput: { 'aria-label': 'Search tenants' } }}
            />
          </Box>
        )}
        {searchable && shown.length === 0 && <MenuItem disabled>No matching tenant</MenuItem>}
        {shown.map((o) => {
          const key = serializeMode(o.mode);
          return (
            // eslint-disable-next-line no-restricted-syntax -- navigation over the user's own /me contexts (not a form field); searchable above SWITCHER_SEARCH_THRESHOLD
            <MenuItem
              key={key}
              selected={key === current}
              onClick={() => {
                void choose(o.mode);
              }}
            >
              <ListItemText primary={o.primary} secondary={o.secondary} />
            </MenuItem>
          );
        })}
      </Menu>
    </>
  );
}
