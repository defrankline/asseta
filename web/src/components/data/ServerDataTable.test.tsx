import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Page } from '../../api/types';
import { ServerDataTable, type DataColumn } from './ServerDataTable';
import type { ServerQuery } from './useServerPage';

interface Row {
  id: string;
  name: string;
}

const columns: DataColumn<Row>[] = [
  { id: 'name', header: 'Name', sortField: 'name', render: (r) => r.name },
];

function pageOf(query: ServerQuery, total = 60): Page<Row> {
  const items = Array.from({ length: Math.min(query.page_size, 3) }, (_, i) => ({
    id: `${String(query.page)}-${String(i)}`,
    name: `Row p${String(query.page)} #${String(i)}`,
  }));
  return { items, total, page: query.page, page_size: query.page_size };
}

function setup(fetchPage = vi.fn((q: ServerQuery) => Promise.resolve(pageOf(q)))) {
  render(
    <ServerDataTable<Row>
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(r) => r.id}
      debounceMs={200}
      initialPageSize={10}
      searchPlaceholder="Search machines"
    />,
  );
  return { fetchPage };
}

const lastQuery = (fn: { mock: { calls: [ServerQuery, ...unknown[]][] } }) =>
  fn.mock.calls.at(-1)?.[0];

describe('ServerDataTable', () => {
  it('loads the first page from the server', async () => {
    const { fetchPage } = setup();
    expect(await screen.findByText('Row p1 #0')).toBeInTheDocument();
    expect(fetchPage).toHaveBeenCalledTimes(1);
    expect(lastQuery(fetchPage)).toMatchObject({ page: 1, page_size: 10 });
  });

  it('debounces search into a single request and resets to page 1', async () => {
    const user = userEvent.setup();
    const { fetchPage } = setup();
    await screen.findByText('Row p1 #0');
    await user.click(screen.getByRole('button', { name: /next page/i }));
    await screen.findByText('Row p2 #0');
    const before = fetchPage.mock.calls.length;

    await user.type(screen.getByRole('textbox', { name: 'Search machines' }), 'cat');
    // Typing is faster than the debounce: nothing sent yet.
    expect(fetchPage.mock.calls.length).toBe(before);
    await waitFor(() => {
      expect(lastQuery(fetchPage)).toMatchObject({ q: 'cat', page: 1 });
    });
    expect(fetchPage.mock.calls.length).toBe(before + 1);
  });

  it('requests the next page and new page size from the server', async () => {
    const user = userEvent.setup();
    const { fetchPage } = setup();
    await screen.findByText('Row p1 #0');
    await user.click(screen.getByRole('button', { name: /next page/i }));
    await waitFor(() => {
      expect(lastQuery(fetchPage)).toMatchObject({ page: 2, page_size: 10 });
    });
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: '25' }));
    await waitFor(() => {
      expect(lastQuery(fetchPage)).toMatchObject({ page: 1, page_size: 25 });
    });
  });

  it('sends server sort when a sortable header is clicked', async () => {
    const user = userEvent.setup();
    const { fetchPage } = setup();
    await screen.findByText('Row p1 #0');
    await user.click(screen.getByRole('button', { name: 'Name' }));
    await waitFor(() => {
      expect(lastQuery(fetchPage)).toMatchObject({ sort: 'name' });
    });
    await user.click(screen.getByRole('button', { name: 'Name' }));
    await waitFor(() => {
      expect(lastQuery(fetchPage)).toMatchObject({ sort: '-name' });
    });
  });

  it('shows empty and error states', async () => {
    const empty = vi.fn((q: ServerQuery) => Promise.resolve({ ...pageOf(q, 0), items: [] }));
    const { unmount } = render(
      <ServerDataTable<Row>
        columns={columns}
        fetchPage={empty}
        getRowId={(r) => r.id}
        emptyTitle="Nothing here"
      />,
    );
    expect(await screen.findByText('Nothing here')).toBeInTheDocument();
    unmount();
    const failing = vi.fn(() => Promise.reject(new Error('boom')));
    render(<ServerDataTable<Row> columns={columns} fetchPage={failing} getRowId={(r) => r.id} />);
    expect(await screen.findByText('Could not load data')).toBeInTheDocument();
  });
});
