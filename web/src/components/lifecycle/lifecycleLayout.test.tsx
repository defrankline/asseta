import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { inactiveFilter } from '../../api/lifecycle';
import { renderWithProviders } from '../../test/renderWithProviders';
import { ServerDataTable } from '../data/ServerDataTable';
import type { ServerQuery } from '../data/useServerPage';
import { ActionButtons } from './ActionButtons';
import { ActiveChip } from './ActiveChip';
import { DetailSection, EntityDetailsLayout } from './EntityDetailsLayout';
import { RowActionsMenu } from './RowActionsMenu';
import { standardRowActions } from './rowActions';
import { ShowInactiveToggle } from './ShowInactiveToggle';

interface Row {
  id: string;
  name: string;
  is_active: boolean;
}

describe('standardRowActions', () => {
  const handlers = {
    onView: vi.fn(),
    onEdit: vi.fn(),
    onDeactivate: vi.fn(),
    onReactivate: vi.fn(),
  };
  const keys = (active: boolean, can: boolean) =>
    standardRowActions({ ...handlers, active, canEdit: can, canChangeState: can }).map(
      (a) => a.key,
    );

  it('offers edit and deactivate on active records', () => {
    expect(keys(true, true)).toEqual(['view', 'edit', 'deactivate']);
  });
  it('offers only reactivate on inactive records', () => {
    expect(keys(false, true)).toEqual(['view', 'reactivate']);
  });
  it('hides every mutation without permission', () => {
    expect(keys(true, false)).toEqual(['view']);
    expect(keys(false, false)).toEqual(['view']);
  });
});

describe('RowActionsMenu', () => {
  it('runs the chosen action without triggering the row click', async () => {
    const user = userEvent.setup();
    const onRow = vi.fn();
    const onEdit = vi.fn();
    renderWithProviders(
      <div onClick={onRow}>
        <RowActionsMenu
          label="Acme"
          actions={[
            { key: 'edit', label: 'Edit', onClick: onEdit },
            { key: 'secret', label: 'Secret', onClick: vi.fn(), hidden: true },
            { key: 'deactivate', label: 'Deactivate', onClick: vi.fn(), destructive: true },
          ]}
        />
      </div>,
    );
    await user.click(screen.getByRole('button', { name: 'Actions for Acme' }));
    expect(screen.queryByRole('menuitem', { name: 'Secret' })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Deactivate' })).toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onRow).not.toHaveBeenCalled();
  });

  it('renders nothing when every action is hidden', () => {
    renderWithProviders(
      <RowActionsMenu
        label="Acme"
        actions={[{ key: 'edit', label: 'Edit', onClick: vi.fn(), hidden: true }]}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Actions for Acme' })).not.toBeInTheDocument();
  });
});

describe('ActionButtons', () => {
  it('renders visible actions as buttons', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    renderWithProviders(
      <ActionButtons
        actions={[
          { key: 'edit', label: 'Edit', onClick: onEdit },
          { key: 'gone', label: 'Gone', onClick: vi.fn(), hidden: true },
        ]}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Gone' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Edit' }));
    expect(onEdit).toHaveBeenCalled();
  });
});

function InactiveList({ fetchPage }: { fetchPage: (q: ServerQuery) => Promise<unknown> }) {
  const [show, setShow] = useState(false);
  return (
    <ServerDataTable<Row>
      columns={[
        { id: 'name', header: 'Name', render: (r) => r.name },
        { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
      ]}
      fetchPage={async (q) => {
        await fetchPage(q);
        return {
          items: [
            { id: '1', name: 'Alpha', is_active: true },
            { id: '2', name: 'Beta', is_active: false },
          ],
          total: 2,
          page: 1,
          page_size: 25,
        };
      }}
      getRowId={(r) => r.id}
      filters={inactiveFilter(show)}
      isRowMuted={(r) => !r.is_active}
      toolbar={<ShowInactiveToggle checked={show} onChange={setShow} />}
    />
  );
}

describe('ShowInactiveToggle with a server table', () => {
  it('sends include_inactive=true to the service only when switched on', async () => {
    const user = userEvent.setup();
    const fetchPage = vi.fn<(q: ServerQuery) => Promise<unknown>>().mockResolvedValue(null);
    renderWithProviders(<InactiveList fetchPage={fetchPage} />);
    expect(await screen.findByText('Alpha')).toBeInTheDocument();
    expect(fetchPage.mock.calls[0]?.[0].filters).toEqual({ include_inactive: undefined });
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(fetchPage.mock.lastCall?.[0].filters).toEqual({ include_inactive: 'true' });
    });
  });

  it('mutes inactive rows and labels them', async () => {
    renderWithProviders(<InactiveList fetchPage={() => Promise.resolve(null)} />);
    const beta = (await screen.findByText('Beta')).closest('tr');
    expect(beta).toHaveAttribute('data-muted', 'true');
    expect(screen.getByText('Alpha').closest('tr')).not.toHaveAttribute('data-muted');
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });
});

describe('EntityDetailsLayout', () => {
  it('shows title, status, actions, sections and the inactive banner', () => {
    renderWithProviders(
      <EntityDetailsLayout
        title="Acme"
        back={{ label: 'All customers', to: '/tenant/customers' }}
        status={<ActiveChip active={false} />}
        actions={<button type="button">Reactivate</button>}
        inactive={{ title: 'This customer is inactive.', reason: 'Bankrupt', since: '1 Oct 2026' }}
      >
        <DetailSection title="Contact">fields</DetailSection>
      </EntityDetailsLayout>,
    );
    expect(screen.getByRole('heading', { name: 'Acme', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'All customers' })).toHaveAttribute(
      'href',
      '/tenant/customers',
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'This customer is inactive. Since 1 Oct 2026. Reason: Bankrupt',
    );
    expect(screen.getByRole('region', { name: 'Contact' })).toHaveTextContent('fields');
    expect(screen.getByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
  });
});
