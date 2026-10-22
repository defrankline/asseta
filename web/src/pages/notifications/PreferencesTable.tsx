import LockOutlined from '@mui/icons-material/LockOutlined';
import {
  Box,
  Chip,
  Paper,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import type { NotificationPreferenceDto } from '../../api/types';
import {
  categoryLabel,
  effective,
  groupByCategory,
  isLocked,
  LOW_PRIORITY_HINT,
  MANDATORY_HINT,
  type Channel,
  type Draft,
} from './preferences';

interface PreferencesTableProps {
  prefs: readonly NotificationPreferenceDto[];
  draft: Draft;
  onToggle: (p: NotificationPreferenceDto, channel: Channel, value: boolean) => void;
  /** Read-only view (e.g. tenant defaults without manage permission). */
  disabled?: boolean;
}

function lockHint(p: NotificationPreferenceDto, channel: Channel): string {
  if (channel === 'sms' && !p.sms_available) return 'In-app only';
  return isLocked(p, channel) ? MANDATORY_HINT : '';
}

/** Per type and channel switches, grouped by category; locked channels are disabled. */
export function PreferencesTable({
  prefs,
  draft,
  onToggle,
  disabled = false,
}: PreferencesTableProps) {
  return (
    <Box className="flex flex-col gap-4">
      {groupByCategory(prefs).map(([category, items]) => {
        const label = categoryLabel(category);
        return (
          <Paper key={category} variant="outlined" component="section" aria-label={label}>
            <Typography variant="subtitle1" component="h2" className="px-4 pt-3">
              {label}
            </Typography>
            <TableContainer>
              <Table size="small" aria-label={`${label} preferences`}>
                <TableHead>
                  <TableRow>
                    <TableCell>Notification</TableCell>
                    <TableCell align="center">In-app</TableCell>
                    <TableCell align="center">SMS</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {items.map((p) => {
                    const value = effective(p, draft);
                    const toggle = (channel: Channel) => (
                      <Tooltip title={lockHint(p, channel)}>
                        <span>
                          <Switch
                            checked={value[channel]}
                            disabled={disabled || isLocked(p, channel)}
                            onChange={(e) => {
                              onToggle(p, channel, e.target.checked);
                            }}
                            slotProps={{
                              input: {
                                'aria-label': `${p.label}: ${channel === 'sms' ? 'SMS' : 'in-app'}`,
                              },
                            }}
                          />
                        </span>
                      </Tooltip>
                    );
                    return (
                      <TableRow key={p.type}>
                        <TableCell>
                          <Box className="flex flex-wrap items-center gap-2">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {p.label}
                            </Typography>
                            {p.mandatory_channels.length > 0 && (
                              <Tooltip title={MANDATORY_HINT}>
                                <Chip
                                  size="small"
                                  icon={<LockOutlined />}
                                  label="Required"
                                  variant="outlined"
                                />
                              </Tooltip>
                            )}
                            {p.low_priority && p.sms_available && (
                              <Tooltip title={LOW_PRIORITY_HINT}>
                                <Chip size="small" label="Low priority" variant="outlined" />
                              </Tooltip>
                            )}
                          </Box>
                          <Typography variant="body2" color="text.secondary">
                            {p.description}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">{toggle('in_app')}</TableCell>
                        <TableCell align="center">{toggle('sms')}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        );
      })}
    </Box>
  );
}
