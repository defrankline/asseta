import LockOutlined from '@mui/icons-material/LockOutlined';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { toApiError } from '../../api/ApiError';
import {
  NOTIFICATION_CATEGORIES,
  notificationChannelService,
  ROUTING_SEVERITIES,
  type ChannelConsole,
} from '../../api/services/notificationChannelService';
import type { NotificationRoutingDto } from '../../api/types';
import { AsyncContent } from '../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { useNotify } from '../../notifications/useNotify';
import {
  CATEGORY_LABELS,
  CHANNEL_LABELS,
  cellKey,
  effectiveCell,
  isLocked,
  routingChanges,
  SEVERITY_LABELS,
  SOURCE_LABELS,
  type RoutingChannel,
  type RoutingDraft,
} from './routing';

const CHANNELS: readonly RoutingChannel[] = ['push', 'email'];

export const MANDATORY_EXPLANATION =
  'Locked channels are required by at least one notification in that row and column ' +
  '(for example, notices about restricted access are always e-mailed), so they stay on.';

interface MatrixProps {
  rows: readonly NotificationRoutingDto[];
  draft: RoutingDraft;
  onToggle: (row: NotificationRoutingDto, channel: RoutingChannel, value: boolean) => void;
  showSource: boolean;
}

function RoutingMatrix({ rows, draft, onToggle, showSource }: MatrixProps) {
  const byCell = new Map(rows.map((r) => [cellKey(r.category, r.severity), r]));
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Push and e-mail by category and severity">
        <TableHead>
          <TableRow>
            <TableCell rowSpan={2}>Category</TableCell>
            {ROUTING_SEVERITIES.map((s) => (
              <TableCell key={s} colSpan={2} align="center">
                {SEVERITY_LABELS[s]}
              </TableCell>
            ))}
          </TableRow>
          <TableRow>
            {ROUTING_SEVERITIES.flatMap((s) =>
              CHANNELS.map((c) => (
                <TableCell key={`${s}-${c}`} align="center">
                  {CHANNEL_LABELS[c]}
                </TableCell>
              )),
            )}
          </TableRow>
        </TableHead>
        <TableBody>
          {NOTIFICATION_CATEGORIES.map((cat) => (
            <TableRow key={cat}>
              <TableCell component="th" scope="row">
                {CATEGORY_LABELS[cat]}
              </TableCell>
              {ROUTING_SEVERITIES.flatMap((sev) =>
                CHANNELS.map((ch) => {
                  const row = byCell.get(cellKey(cat, sev));
                  if (row === undefined) {
                    return (
                      <TableCell key={`${sev}-${ch}`} align="center">
                        —
                      </TableCell>
                    );
                  }
                  const locked = isLocked(row, ch);
                  const value = effectiveCell(row, draft)[ch];
                  const name = `${CHANNEL_LABELS[ch]} for ${CATEGORY_LABELS[cat]}, ${SEVERITY_LABELS[sev]}`;
                  return (
                    <TableCell key={`${sev}-${ch}`} align="center" sx={{ whiteSpace: 'nowrap' }}>
                      <Checkbox
                        size="small"
                        checked={value}
                        disabled={locked}
                        slotProps={{
                          input: {
                            'aria-label': locked ? `${name} (required)` : name,
                          },
                        }}
                        onChange={(e) => {
                          onToggle(row, ch, e.target.checked);
                        }}
                      />
                      {locked && (
                        <Tooltip title="Required: cannot be switched off">
                          <LockOutlined
                            fontSize="inherit"
                            aria-hidden
                            sx={{ verticalAlign: 'middle', color: 'text.secondary' }}
                          />
                        </Tooltip>
                      )}
                      {showSource && ch === 'push' && row.source !== 'USER' && (
                        <Typography variant="caption" color="text.secondary" component="div">
                          {SOURCE_LABELS[row.source] ?? row.source}
                        </Typography>
                      )}
                    </TableCell>
                  );
                }),
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

interface RoutingEditorProps {
  console: ChannelConsole;
  tenantDefault: boolean;
  /** False when the viewer may only look (e.g. tenant defaults without the manage permission). */
  editable?: boolean;
}

/** PUSH / E-MAIL routing per category x severity (`/{console}/notification-routing`). */
export function RoutingEditor({ console, tenantDefault, editable = true }: RoutingEditorProps) {
  const notify = useNotify();
  const keyFor = useIdempotencyKey();
  const load = useCallback(
    (signal: AbortSignal) => notificationChannelService.getRouting(console, tenantDefault, signal),
    [console, tenantDefault],
  );
  const routing = useAsyncResource(load);
  const [draft, setDraft] = useState<RoutingDraft>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const changes = routingChanges(routing.data ?? [], draft);

  const toggle = (row: NotificationRoutingDto, channel: RoutingChannel, value: boolean) => {
    if (!editable) return;
    setDraft((d) => ({
      ...d,
      [cellKey(row.category, row.severity)]: { ...effectiveCell(row, d), [channel]: value },
    }));
  };

  const save = () => {
    const body = { changes, tenant_default: tenantDefault };
    setSaving(true);
    setSaveError(null);
    notificationChannelService
      .updateRouting(console, body, keyFor(body))
      .then(() => {
        notify.success(
          tenantDefault ? 'Tenant routing defaults saved.' : 'Push and e-mail routing saved.',
        );
        setDraft({});
        routing.reload();
      })
      .catch((err: unknown) => {
        const e = toApiError(err);
        setSaveError(e.code === 'MANDATORY_CHANNEL' ? `${e.message} (${e.code})` : e.message);
      })
      .finally(() => {
        setSaving(false);
      });
  };

  return (
    <Box component="section" aria-labelledby="routing-heading" className="flex flex-col gap-3">
      <Box>
        <Typography id="routing-heading" variant="h6" component="h2">
          Push and e-mail
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {tenantDefault
            ? 'Tenant-wide push and e-mail defaults; a user’s own choices take precedence.'
            : 'Which notifications also reach your phone (owner and supervisor apps) and your e-mail. In-app notifications are always on.'}
        </Typography>
      </Box>
      <Alert severity="info" icon={<LockOutlined fontSize="inherit" />}>
        {MANDATORY_EXPLANATION}
      </Alert>
      <AsyncContent
        resource={routing}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No routing options"
        errorTitle="Could not load push and e-mail routing"
      >
        {(rows) => (
          <Box className="flex flex-col gap-3">
            <RoutingMatrix
              rows={rows}
              draft={draft}
              onToggle={toggle}
              showSource={!tenantDefault}
            />
            {saveError !== null && <Alert severity="error">{saveError}</Alert>}
            {editable && (
              <Box className="flex flex-wrap justify-end gap-2">
                <Button
                  disabled={changes.length === 0 || saving}
                  onClick={() => {
                    setDraft({});
                  }}
                >
                  Discard changes
                </Button>
                <Button
                  variant="contained"
                  disabled={changes.length === 0}
                  loading={saving}
                  onClick={save}
                >
                  {tenantDefault ? 'Save routing defaults' : 'Save routing'}
                </Button>
              </Box>
            )}
          </Box>
        )}
      </AsyncContent>
    </Box>
  );
}
