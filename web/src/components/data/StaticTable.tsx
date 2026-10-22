import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { rowClassName } from './rowStyle';
import type { DataColumn } from './ServerDataTable';

interface StaticTableProps<T> {
  columns: readonly DataColumn<T>[];
  rows: readonly T[];
  getRowId: (row: T) => string;
  ariaLabel: string;
  onRowClick?: (row: T) => void;
  /** Inactive records (deactivated, retired, cancelled) are shown muted. */
  isRowMuted?: (row: T) => boolean;
}

/** Small client-side table for short, unpaged lists (rate versions, invoice lines, ...). */
export function StaticTable<T>({
  columns,
  rows,
  getRowId,
  ariaLabel,
  onRowClick,
  isRowMuted,
}: StaticTableProps<T>) {
  return (
    <TableContainer>
      <Table size="small" aria-label={ariaLabel}>
        <TableHead>
          <TableRow>
            {columns.map((c) => (
              <TableCell key={c.id} align={c.align ?? 'left'}>
                {c.header}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={getRowId(row)}
              hover={onRowClick !== undefined}
              className={rowClassName(onRowClick !== undefined, isRowMuted?.(row) === true)}
              data-muted={isRowMuted?.(row) === true ? 'true' : undefined}
              tabIndex={onRowClick !== undefined ? 0 : undefined}
              onKeyDown={
                onRowClick !== undefined
                  ? (e) => {
                      if (e.target !== e.currentTarget) return;
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
              sx={
                onRowClick !== undefined
                  ? {
                      '&:focus-visible': {
                        outline: '2px solid',
                        outlineColor: 'primary.main',
                        outlineOffset: -2,
                      },
                    }
                  : undefined
              }
              onClick={
                onRowClick !== undefined
                  ? () => {
                      onRowClick(row);
                    }
                  : undefined
              }
            >
              {columns.map((c) => (
                <TableCell key={c.id} align={c.align ?? 'left'}>
                  {c.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
