import SearchIcon from '@mui/icons-material/Search';
import { Box, Button, InputAdornment, Paper, TextField } from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../access/permissionCodes';
import type { NotificationSeverity } from '../../api/types';
import { PageHeader } from '../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../components/forms/StaticSelectFilter';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { ROUTES } from '../../navigation/routes';
import { READ_STATE_OPTIONS, SEVERITY_OPTIONS } from '../../notifications/center/display';
import { useNotificationCenter } from '../../notifications/center/NotificationCenterContext';
import { NotificationList } from '../../notifications/center/NotificationList';
import { useNotificationFeed } from '../../notifications/center/useNotificationFeed';
import { useNotify } from '../../notifications/useNotify';
import { useSession } from '../../session/useSession';

/** Full inbox of the signed-in user in the current console, with server-side filters. */
export function NotificationsPage() {
  const notify = useNotify();
  const { unreadCount } = useNotificationCenter();
  const { hasPermission } = useSession();
  const canSeeDeliveries = hasPermission(
    [PERMISSIONS.tenantNotificationManage, PERMISSIONS.platformNotificationManage],
    'any',
  );
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const [severity, setSeverity] = useState('');
  const [readState, setReadState] = useState('');
  const [marking, setMarking] = useState(false);
  const feed = useNotificationFeed({
    unreadOnly: readState === 'unread',
    ...(severity !== '' ? { severity: severity as NotificationSeverity } : {}),
    q,
  });

  const markAll = () => {
    setMarking(true);
    feed
      .markAllRead()
      .then(() => {
        notify.success('All notifications marked as read.');
      })
      .catch((err: unknown) => {
        notify.error(err, 'Could not mark all notifications as read.');
      })
      .finally(() => {
        setMarking(false);
      });
  };

  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle="Actions to take, reminders and anomalies for the current console"
        actions={
          <>
            {canSeeDeliveries && (
              <Button component={RouterLink} to={ROUTES.notificationDeliveries}>
                Delivery log
              </Button>
            )}
            <Button component={RouterLink} to={ROUTES.notificationPreferences}>
              Preferences
            </Button>
            <Button
              variant="contained"
              onClick={markAll}
              loading={marking}
              disabled={unreadCount === 0 || unreadCount === null}
            >
              Mark all read
            </Button>
          </>
        }
      />
      <Box className="mb-3 flex flex-wrap items-center gap-3">
        <TextField
          size="small"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
          }}
          placeholder="Search notifications"
          slotProps={{
            htmlInput: { 'aria-label': 'Search notifications' },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <StaticSelectFilter
          label="Severity"
          value={severity}
          options={SEVERITY_OPTIONS}
          onChange={setSeverity}
        />
        <StaticSelectFilter
          label="Status"
          value={readState}
          options={READ_STATE_OPTIONS}
          onChange={setReadState}
          allLabel="All"
        />
      </Box>
      <Paper variant="outlined">
        <NotificationList
          feed={feed}
          emptyTitle={readState === 'unread' ? 'No unread notifications' : 'No notifications match'}
        />
      </Paper>
    </>
  );
}
