import FileDownloadOutlined from '@mui/icons-material/FileDownloadOutlined';
import { Button, ListItemText, ListSubheader, Menu, MenuItem } from '@mui/material';
import { useCallback, useId, useState } from 'react';
import {
  reportService,
  type ReportConsole,
  type ReportFormat,
} from '../../api/services/reportService';
import type { ReportDefinitionDto } from '../../api/types';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { useNotify } from '../../notifications/useNotify';
import { useSession } from '../../session/useSession';
import { exportParams, saveBlob, type ExportRequest } from './exportFile';

export type { ExportRequest } from './exportFile';

interface ExportMenuProps {
  reports: readonly ExportRequest[];
  label?: string;
}

const FORMATS: readonly ReportFormat[] = ['csv', 'pdf'];

interface Choice {
  definition: ReportDefinitionDto;
  request: ExportRequest;
  format: ReportFormat;
}

/**
 * "Export" menu (CSV / PDF) for the page's reports. Lists only reports the caller may export
 * (`GET /{console}/reports`), sends the page's current filters, and reports a capped export.
 */
export function ExportMenu({ reports, label = 'Export' }: ExportMenuProps) {
  const { mode, activeTenant } = useSession();
  const notify = useNotify();
  const menuId = useId();
  const reportConsole: ReportConsole | null =
    mode.kind === 'platform' ? 'platform' : mode.kind === 'tenant' ? 'tenant' : null;
  const cacheKey = activeTenant?.tenant_id ?? 'platform';
  const load = useCallback(
    () =>
      reportConsole === null
        ? Promise.resolve([])
        : reportService.listDefinitions(reportConsole, cacheKey),
    [reportConsole, cacheKey],
  );
  const definitions = useAsyncResource(load);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);

  const choices: Choice[] = reports.flatMap((request) => {
    const definition = definitions.data?.find((d) => d.code === request.code);
    if (definition === undefined) return [];
    return FORMATS.filter((f) => definition.formats.includes(f)).map((format) => ({
      definition,
      request,
      format,
    }));
  });
  if (reportConsole === null || choices.length === 0) return null;

  const run = async ({ definition, request, format }: Choice) => {
    setAnchor(null);
    setBusy(true);
    try {
      const file = await reportService.download(
        reportConsole,
        definition.code,
        format,
        exportParams(definition, request.filters),
      );
      saveBlob(file.blob, file.filename);
      const cap = format === 'csv' ? definition.csv_row_cap : definition.pdf_row_cap;
      const rows = file.rows ?? cap;
      if (file.truncated) {
        notify.warning(
          `${definition.title}: export truncated to the first ${rows.toLocaleString()} rows ` +
            `(${format.toUpperCase()} limit). Narrow the filters to export the rest.`,
        );
      } else {
        notify.success(
          `${definition.title}: exported ${rows.toLocaleString()} ${rows === 1 ? 'row' : 'rows'}.`,
        );
      }
    } catch (err) {
      notify.error(err, `Could not export ${definition.title}.`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        variant="outlined"
        startIcon={<FileDownloadOutlined />}
        aria-haspopup="menu"
        aria-controls={anchor !== null ? menuId : undefined}
        aria-expanded={anchor !== null}
        loading={busy}
        onClick={(e) => {
          setAnchor(e.currentTarget);
        }}
      >
        {label}
      </Button>
      <Menu
        id={menuId}
        anchorEl={anchor}
        open={anchor !== null}
        onClose={() => {
          setAnchor(null);
        }}
      >
        <ListSubheader>Uses the filters shown on this page</ListSubheader>
        {choices.map((choice) => (
          // eslint-disable-next-line no-restricted-syntax -- an action menu (download choices), not a form dropdown
          <MenuItem
            key={`${choice.definition.code}.${choice.format}`}
            onClick={() => {
              void run(choice);
            }}
          >
            <ListItemText
              primary={`${choice.definition.title} (${choice.format.toUpperCase()})`}
              secondary={`Up to ${(choice.format === 'csv'
                ? choice.definition.csv_row_cap
                : choice.definition.pdf_row_cap
              ).toLocaleString()} rows`}
            />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
