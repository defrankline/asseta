import { List, ListItem, ListItemText, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import type { AsyncResource } from '../../../hooks/useAsyncResource';
import { formatInstantIn } from '../../../utils/time';

/** One step of a record's life (requested, answered, decided, …); steps without a time are skipped. */
export interface HistoryEvent {
  key: string;
  at: string | null | undefined;
  label: string;
  /** Who did it (usually a `<PersonName>`). */
  by?: ReactNode;
  note?: string | null | undefined;
}

/** A record's history, oldest first. */
export function HistoryList({ events, timeZone }: { events: HistoryEvent[]; timeZone: string }) {
  const shown = events
    .filter((e): e is HistoryEvent & { at: string } => e.at != null && e.at !== '')
    .sort((a, b) => a.at.localeCompare(b.at));
  if (shown.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No history yet.
      </Typography>
    );
  }
  return (
    <List dense disablePadding aria-label="History">
      {shown.map((e) => (
        <ListItem key={e.key} disableGutters alignItems="flex-start">
          <ListItemText
            primary={
              <>
                <strong>{e.label}</strong>
                {e.by !== undefined && <> · {e.by}</>}
              </>
            }
            secondary={
              <>
                {formatInstantIn(e.at, timeZone)}
                {e.note != null && e.note !== '' && ` · ${e.note}`}
              </>
            }
          />
        </ListItem>
      ))}
    </List>
  );
}

interface RecordDetailProps<T> {
  resource: AsyncResource<T>;
  /** e.g. "cash transfer" (loading / error wording). */
  what: string;
  back: { label: string; to: string };
  timeZone: string;
  title: (r: T) => string;
  subtitle?: (r: T) => string;
  status?: (r: T) => ReactNode;
  /** The same commands as the list row's menu (permission-gated, own requests disabled). */
  actions?: (r: T) => RowAction[];
  primaryKey?: string;
  /** Links next to the commands (e.g. "Engine hours"). */
  links?: (r: T) => ReactNode;
  items: (r: T) => KeyValueItem[];
  history: (r: T) => HistoryEvent[];
  /** Extra sections below the details. */
  children?: (r: T) => ReactNode;
}

/** Detail page of one accountability record: names, status, the row's commands and its history. */
export function RecordDetail<T>({
  resource,
  what,
  back,
  timeZone,
  title,
  subtitle,
  status,
  actions,
  primaryKey,
  links,
  items,
  history,
  children,
}: RecordDetailProps<T>) {
  return (
    <AsyncContent
      resource={resource}
      loadingLabel={`Loading ${what}`}
      errorTitle={`Could not load this ${what}`}
    >
      {(r) => (
        <EntityDetailsLayout
          title={title(r)}
          {...(subtitle === undefined ? {} : { subtitle: subtitle(r) })}
          back={back}
          status={status?.(r)}
          actions={
            <div className="flex flex-col items-end gap-2">
              {links?.(r)}
              {actions !== undefined && (
                <ActionButtons
                  actions={actions(r)}
                  {...(primaryKey === undefined ? {} : { primaryKey })}
                />
              )}
            </div>
          }
        >
          <DetailSection title="Details">
            <KeyValueGrid columns={2} items={items(r)} />
          </DetailSection>
          {children?.(r)}
          <DetailSection title="History">
            <HistoryList events={history(r)} timeZone={timeZone} />
          </DetailSection>
        </EntityDetailsLayout>
      )}
    </AsyncContent>
  );
}
