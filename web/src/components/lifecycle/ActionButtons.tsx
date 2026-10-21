import { Box, Button } from '@mui/material';
import type { RowAction } from './rowActions';

interface ActionButtonsProps {
  actions: readonly RowAction[];
  /** Key of the action rendered as the contained primary button (default: `edit`). */
  primaryKey?: string;
}

/** The same record commands as a row menu, laid out as buttons (details pages and drawers). */
export function ActionButtons({ actions, primaryKey = 'edit' }: ActionButtonsProps) {
  const visible = actions.filter((a) => a.hidden !== true);
  if (visible.length === 0) return null;
  return (
    <Box className="flex flex-wrap gap-2">
      {visible.map((a) => (
        <Button
          key={a.key}
          size="small"
          variant={a.key === primaryKey ? 'contained' : 'outlined'}
          color={a.destructive === true ? 'error' : 'primary'}
          disabled={a.disabled === true}
          startIcon={a.icon}
          onClick={a.onClick}
        >
          {a.label}
        </Button>
      ))}
    </Box>
  );
}
