import MoreVert from '@mui/icons-material/MoreVert';
import { Box, IconButton, ListItemIcon, ListItemText, Menu, MenuItem } from '@mui/material';
import { useState } from 'react';
import type { RowAction } from './rowActions';

interface RowActionsMenuProps {
  /** Record label for the accessible button name, e.g. `EX-01 · Excavator`. */
  label: string;
  actions: readonly RowAction[];
}

/**
 * Kebab menu of record commands for a table row. Clicks never reach the row (rows navigate to
 * details). Renders nothing when every action is hidden.
 */
export function RowActionsMenu({ label, actions }: RowActionsMenuProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const visible = actions.filter((a) => a.hidden !== true);
  if (visible.length === 0) return null;
  const close = () => {
    setAnchor(null);
  };
  return (
    <Box
      component="span"
      onClick={(e) => {
        e.stopPropagation();
      }}
    >
      <IconButton
        size="small"
        aria-label={`Actions for ${label}`}
        aria-haspopup="menu"
        onClick={(e) => {
          setAnchor(e.currentTarget);
        }}
      >
        <MoreVert fontSize="small" />
      </IconButton>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={close}>
        {visible.map((a) => (
          // eslint-disable-next-line no-restricted-syntax -- code-defined record commands, not backend options
          <MenuItem
            key={a.key}
            disabled={a.disabled === true}
            sx={a.destructive === true ? { color: 'error.main' } : undefined}
            onClick={() => {
              close();
              a.onClick();
            }}
          >
            {a.icon !== undefined && <ListItemIcon>{a.icon}</ListItemIcon>}
            <ListItemText>{a.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
