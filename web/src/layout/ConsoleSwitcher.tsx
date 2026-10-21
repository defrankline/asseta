import { MenuItem, TextField } from '@mui/material';
import { parseMode, serializeMode } from '../session/permissions';
import { useSession } from '../session/useSession';

/** Selects the active tenant, or Platform console when the user holds platform permissions. */
export function ConsoleSwitcher() {
  const { me, mode, canUsePlatform, setMode } = useSession();
  if (me === null) return null;
  const optionCount = me.tenants.length + (canUsePlatform ? 1 : 0);
  if (optionCount === 0) return null;

  return (
    <TextField
      select
      size="small"
      label="Console"
      value={mode.kind === 'none' ? '' : serializeMode(mode)}
      onChange={(e) => {
        const next = parseMode(e.target.value);
        if (next !== null) setMode(next);
      }}
      className="min-w-56"
      sx={{
        '& .MuiInputBase-root': { color: 'inherit', bgcolor: 'rgba(255,255,255,0.08)' },
        '& .MuiInputLabel-root, & .MuiSvgIcon-root': { color: 'inherit' },
      }}
    >
      {canUsePlatform && <MenuItem value="platform">Platform console</MenuItem>}
      {me.tenants.map((t) => (
        <MenuItem
          key={t.tenant_id}
          value={serializeMode({ kind: 'tenant', tenantId: t.tenant_id })}
        >
          {t.name}
          {t.access_state !== 'FULL' ? ` (${t.access_state.replace('_', ' ').toLowerCase()})` : ''}
        </MenuItem>
      ))}
    </TextField>
  );
}
