import Close from '@mui/icons-material/Close';
import {
  Box,
  Button,
  Divider,
  Drawer,
  FormControlLabel,
  IconButton,
  Switch,
  Toolbar,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { ROUTES } from '../../navigation/routes';
import { useNotify } from '../useNotify';
import { useNotificationCenter } from './NotificationCenterContext';
import { NotificationList } from './NotificationList';
import { useNotificationFeed } from './useNotificationFeed';

export const DRAWER_WIDTH = 400;

interface NotificationDrawerProps {
  onClose: () => void;
}

/** Inbox drawer (mount only while open so it loads fresh). */
export function NotificationDrawer({ onClose }: NotificationDrawerProps) {
  const notify = useNotify();
  const { unreadCount } = useNotificationCenter();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const feed = useNotificationFeed({ unreadOnly }, 15);
  const [marking, setMarking] = useState(false);

  const markAll = () => {
    setMarking(true);
    feed
      .markAllRead()
      .catch((err: unknown) => {
        notify.error(err, 'Could not mark all notifications as read.');
      })
      .finally(() => {
        setMarking(false);
      });
  };

  return (
    <Drawer
      anchor="right"
      open
      onClose={onClose}
      slotProps={{ paper: { sx: { width: { xs: '100%', sm: DRAWER_WIDTH } } } }}
    >
      <Toolbar />
      <Box
        className="flex items-center justify-between gap-2 px-4 py-2"
        role="region"
        aria-label="Notifications inbox"
      >
        <Typography variant="h6" component="h2">
          Notifications
        </Typography>
        <IconButton aria-label="Close notifications" onClick={onClose}>
          <Close />
        </IconButton>
      </Box>
      <Box className="flex flex-wrap items-center justify-between gap-2 px-4 pb-2">
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={unreadOnly}
              onChange={(e) => {
                setUnreadOnly(e.target.checked);
              }}
            />
          }
          label="Unread only"
        />
        <Button
          size="small"
          onClick={markAll}
          loading={marking}
          disabled={unreadCount === 0 || unreadCount === null}
        >
          Mark all read
        </Button>
      </Box>
      <Divider />
      <Box className="flex-1 overflow-y-auto">
        <NotificationList
          feed={feed}
          dense
          onNavigate={onClose}
          emptyTitle={unreadOnly ? 'No unread notifications' : 'No notifications'}
        />
      </Box>
      <Divider />
      <Box className="flex justify-between gap-2 px-4 py-2">
        <Button component={RouterLink} to={ROUTES.notifications} onClick={onClose} size="small">
          View all
        </Button>
        <Button
          component={RouterLink}
          to={ROUTES.notificationPreferences}
          onClick={onClose}
          size="small"
        >
          Preferences
        </Button>
      </Box>
    </Drawer>
  );
}
