import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import type { DataColumn } from './ServerDataTable';

interface StaticTableProps<T> {
  columns: readonly DataColumn<T>[];
  rows: readonly T[];
  getRowId: (row: T) => string;
  ariaLabel: string;
}

/** Small client-side table for short, unpaged lists (rate versions, invoice lines, ...). */
export function StaticTable<T>({ columns, rows, getRowId, ariaLabel }: StaticTableProps<T>) {
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
            <TableRow key={getRowId(row)}>
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
