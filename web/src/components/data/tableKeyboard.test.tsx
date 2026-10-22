import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ServerDataTable, type DataColumn } from './ServerDataTable';
import { StaticTable } from './StaticTable';

interface Row {
  id: string;
  name: string;
}

const columns: DataColumn<Row>[] = [{ id: 'name', header: 'Name', render: (r) => r.name }];
const rows: Row[] = [
  { id: 'a', name: 'Alpha' },
  { id: 'b', name: 'Bravo' },
];

describe('table accessibility', () => {
  it('makes clickable server-table rows focusable and operable with Enter / Space', async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    const onSearchChange = vi.fn();
    render(
      <ServerDataTable<Row>
        columns={columns}
        fetchPage={() => Promise.resolve({ items: rows, total: 2, page: 1, page_size: 25 })}
        getRowId={(r) => r.id}
        onRowClick={onRowClick}
        onSearchChange={onSearchChange}
        debounceMs={0}
      />,
    );
    const row = (await screen.findByText('Alpha')).closest('tr');
    expect(row).toHaveAttribute('tabindex', '0');
    (row as HTMLElement).focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');
    expect(onRowClick).toHaveBeenCalledTimes(2);
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);
    await user.type(screen.getByRole('textbox', { name: 'Search' }), 'x');
    await waitFor(() => {
      expect(onSearchChange).toHaveBeenLastCalledWith('x');
    });
  });

  it('does the same for static tables, and leaves plain rows out of the tab order', async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    const { rerender } = render(
      <StaticTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        ariaLabel="Things"
        onRowClick={onRowClick}
      />,
    );
    const row = screen.getByText('Bravo').closest('tr') as HTMLElement;
    row.focus();
    await user.keyboard('{Enter}');
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
    rerender(
      <StaticTable columns={columns} rows={rows} getRowId={(r) => r.id} ariaLabel="Things" />,
    );
    expect(screen.getByText('Bravo').closest('tr')).not.toHaveAttribute('tabindex');
  });
});
