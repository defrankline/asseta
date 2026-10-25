import DoneOutlined from '@mui/icons-material/DoneOutlined';
import {
  Box,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  Tooltip,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router';
import { useDisabledCapabilities } from '../../access/capabilities';
import type { NotificationDto } from '../../api/types';
import { AgeText } from '../../components/display/AgeText';
import { EmptyState } from '../../components/feedback/EmptyState';
import { ErrorState } from '../../components/feedback/ErrorState';
import { LoadingState } from '../../components/feedback/LoadingState';
import { useDisplayTimeZone } from '../../hooks/useDisplayTimeZone';
import { useNow } from '../../hooks/useNow';
import { useNotify } from '../useNotify';
import { notificationTargetPath, SEVERITY_META } from './display';
import type { NotificationFeed } from './useNotificationFeed';

interface NotificationListProps {
  feed: NotificationFeed;
  /** Called after following a notification's link (e.g. to close the drawer). */
  onNavigate?: () => void;
  emptyTitle?: string;
  dense?: boolean;
}

/** Inbox list: severity colour + icon + label, read state, mark read, link, load more. */
export function NotificationList({
  feed,
  onNavigate,
  emptyTitle = 'No notifications',
  dense = false,
}: NotificationListProps) {
  const navigate = useNavigate();
  const notify = useNotify();
  const disabled = useDisabledCapabilities();
  const now = useNow();
  const timeZone = useDisplayTimeZone();

  if (feed.error !== null && feed.items.length === 0) {
    return (
      <ErrorState error={feed.error} title="Could not load notifications" onRetry={feed.reload} />
    );
  }
  if (feed.loading && feed.items.length === 0)
    return <LoadingState label="Loading notifications" />;
  if (feed.items.length === 0) return <EmptyState title={emptyTitle} />;

  const markRead = (n: NotificationDto) => {
    feed.markRead(n).catch((err: unknown) => {
      notify.error(err, 'Could not mark the notification as read.');
    });
  };
  const open = (n: NotificationDto, path: string) => {
    markRead(n);
    void navigate(path);
    onNavigate?.();
  };

  return (
    <Box>
      <List dense={dense} aria-label="Notifications" disablePadding>
        {feed.items.map((n) => {
          const meta = SEVERITY_META[n.severity];
          const unread = n.read_at === null;
          const path = notificationTargetPath(n.target, n.data, disabled);
          const body = (
            <Box className="flex min-w-0 flex-1 gap-3">
              <Box sx={{ color: `${meta.color}.main`, pt: 0.25 }} aria-hidden>
                {meta.icon}
              </Box>
              <Box className="min-w-0 flex-1">
                <Typography
                  variant="body2"
                  sx={{ fontWeight: unread ? 700 : 400, overflowWrap: 'anywhere' }}
                >
                  {n.title}
                </Typography>
                {n.body !== '' && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ overflowWrap: 'anywhere' }}
                  >
                    {n.body}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary">
                  {meta.label} · <AgeText at={n.created_at} now={now} timeZone={timeZone} />
                  {unread ? ' · Unread' : ''}
                </Typography>
              </Box>
            </Box>
          );
          return (
            <ListItem
              key={n.id}
              disablePadding
              divider
              data-unread={unread ? 'true' : 'false'}
              sx={{
                borderLeft: 4,
                borderLeftColor: unread ? `${meta.color}.main` : 'transparent',
                bgcolor: unread ? 'action.hover' : undefined,
              }}
              secondaryAction={
                unread ? (
                  <Tooltip title="Mark as read">
                    <IconButton
                      edge="end"
                      size="small"
                      aria-label={`Mark "${n.title}" as read`}
                      onClick={() => {
                        markRead(n);
                      }}
                    >
                      <DoneOutlined fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ) : undefined
              }
            >
              {path !== null ? (
                <ListItemButton
                  aria-label={`Open: ${n.title}`}
                  onClick={() => {
                    open(n, path);
                  }}
                  sx={{ alignItems: 'flex-start', pr: 6 }}
                >
                  {body}
                </ListItemButton>
              ) : (
                <Box className="flex w-full px-4 py-2" sx={{ pr: 6 }}>
                  {body}
                </Box>
              )}
            </ListItem>
          );
        })}
      </List>
      {feed.error !== null && (
        <Typography role="alert" variant="body2" color="error" className="px-4 py-2">
          {feed.error.message}
        </Typography>
      )}
      {feed.hasMore && (
        <Box className="flex justify-center py-2">
          <Button onClick={feed.loadMore} loading={feed.loadingMore}>
            Load more
          </Button>
        </Box>
      )}
    </Box>
  );
}
