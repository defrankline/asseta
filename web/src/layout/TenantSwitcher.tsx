import ExpandMore from '@mui/icons-material/ExpandMore';
import SwapHoriz from '@mui/icons-material/SwapHoriz';
import { Button, ListItemText, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { TenantAccess } from '../api/types';
import { ROUTES } from '../navigation/routes';
import { mandateScopeLabel } from '../session/mandateDisplay';
import { serializeMode, type ConsoleMode } from '../session/permissions';
import { useSession } from '../session/useSession';

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
 * Header "Switch tenant" menu. Platform staff see their own context ("Your tenant", the platform
 * console) first, then each client they may act for under an in-force mandate (from /me only).
 */
export function TenantSwitcher() {
  const { me, mode, activeTenant, canUsePlatform, setMode } = useSession();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  if (me === null) return null;

  const options: SwitchOption[] = [
    ...(canUsePlatform
      ? [
          {
            mode: { kind: 'platform' } as const,
            primary: 'Your tenant',
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
    mode.kind === 'platform' ? 'Your tenant' : (activeTenant?.name ?? 'Select a tenant');

  const choose = async (next: ConsoleMode) => {
    setAnchor(null);
    if (serializeMode(next) === current) return;
    await setMode(next);
    void navigate(ROUTES.home);
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
        sx={{ textTransform: 'none', bgcolor: 'rgba(255,255,255,0.08)', maxWidth: 320 }}
      >
        <span className="truncate">{label}</span>
      </Button>
      <Menu
        id="tenant-switch-menu"
        anchorEl={anchor}
        open={anchor !== null}
        onClose={() => {
          setAnchor(null);
        }}
      >
        {options.map((o) => {
          const key = serializeMode(o.mode);
          return (
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
