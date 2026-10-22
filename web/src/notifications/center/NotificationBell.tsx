import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';
import { Badge, IconButton, Tooltip } from '@mui/material';
import { useState } from 'react';
import { useOptionalNotificationCenter } from './NotificationCenterContext';
import { NotificationDrawer } from './NotificationDrawer';

function bellLabel(count: number | null): string {
  if (count === null || count === 0) return 'Notifications';
  return `Notifications (${String(count)} unread)`;
}

/** Header bell with the unread badge; opens the inbox drawer. Hidden outside a center provider. */
export function NotificationBell() {
  const center = useOptionalNotificationCenter();
  const [open, setOpen] = useState(false);
  if (center?.enabled !== true) return null;
  const count = center.unreadCount;
  const label = bellLabel(count);
  return (
    <>
      <Tooltip title={label}>
        <IconButton
          color="inherit"
          aria-label={label}
          aria-haspopup="dialog"
          onClick={() => {
            setOpen(true);
          }}
        >
          <Badge badgeContent={count ?? 0} max={99} color="error">
            <NotificationsOutlined />
          </Badge>
        </IconButton>
      </Tooltip>
      {open && (
        <NotificationDrawer
          onClose={() => {
            setOpen(false);
          }}
        />
      )}
    </>
  );
}
