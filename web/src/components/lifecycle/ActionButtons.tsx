import { Box, Button, Tooltip, Typography } from '@mui/material';
import { useId } from 'react';
import type { RowAction } from './rowActions';

interface ActionButtonsProps {
  actions: readonly RowAction[];
  /** Key of the action rendered as the contained primary button (default: `edit`). */
  primaryKey?: string;
}

/**
 * The same record commands as a row menu, laid out as buttons (details pages and drawers). A
 * disabled command with a `disabledReason` explains itself in a tooltip and in helper text below.
 */
export function ActionButtons({ actions, primaryKey = 'edit' }: ActionButtonsProps) {
  const idPrefix = useId();
  const visible = actions.filter((a) => a.hidden !== true);
  if (visible.length === 0) return null;
  const explained = visible.filter((a) => a.disabled === true && a.disabledReason !== undefined);
  const reasonId = (a: RowAction) => `${idPrefix}-${a.key}-reason`;
  return (
    <Box className="flex flex-col gap-1">
      <Box className="flex flex-wrap gap-2">
        {visible.map((a) => {
          const button = (
            <Button
              key={a.key}
              size="small"
              variant={a.key === primaryKey ? 'contained' : 'outlined'}
              color={a.destructive === true ? 'error' : 'primary'}
              disabled={a.disabled === true}
              startIcon={a.icon}
              onClick={a.onClick}
              aria-describedby={explained.includes(a) ? reasonId(a) : undefined}
            >
              {a.label}
            </Button>
          );
          if (!explained.includes(a)) return button;
          return (
            <Tooltip key={a.key} title={a.disabledReason}>
              {/* Disabled buttons fire no events; the span carries the tooltip. */}
              <span>{button}</span>
            </Tooltip>
          );
        })}
      </Box>
      {explained.map((a) => (
        <Typography key={a.key} id={reasonId(a)} variant="caption" color="text.secondary">
          {a.label} unavailable. {a.disabledReason}
        </Typography>
      ))}
    </Box>
  );
}
