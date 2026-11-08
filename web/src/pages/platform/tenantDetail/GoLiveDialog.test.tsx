import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { dataProtectionService } from '../../../api/services/dataProtectionService';
import type { TenantDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { GoLiveDialog } from './GoLiveDialog';

const m = vi.hoisted(() => ({ markLive: vi.fn<typeof dataProtectionService.markLive>() }));
vi.mock('../../../api/services/dataProtectionService', () => ({ dataProtectionService: m }));

const tenant = {
  id: 't1',
  display_name: 'Acme Hire',
  legal_name: 'Acme Hire Ltd',
  registration_number: null,
  contact_name: 'A',
  contact_email: 'a@example.com',
  contact_phone: null,
  status: 'ACTIVE',
  access_state: 'FULL',
  access_state_reason: null,
  verification_status: 'VERIFIED',
  created_at: '2026-01-01T00:00:00Z',
  version: 1,
} satisfies TenantDto;

describe('GoLiveDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requires the exact company name', async () => {
    m.markLive.mockResolvedValue({ ...tenant, live_at: '2026-11-08T08:00:00Z' });
    const onMarked = vi.fn();
    renderWithProviders(<GoLiveDialog tenant={tenant} onClose={vi.fn()} onMarked={onMarked} />);
    await userEvent.type(screen.getByLabelText(/Company name/), 'Acme');
    await userEvent.click(screen.getByRole('button', { name: 'Mark as live' }));
    expect(await screen.findByText('The name does not match')).toBeInTheDocument();
    expect(m.markLive).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText(/Company name/), ' Hire');
    await userEvent.click(screen.getByRole('button', { name: 'Mark as live' }));
    await waitFor(() => {
      expect(onMarked).toHaveBeenCalled();
    });
    expect(m.markLive.mock.calls[0]?.[1]).toEqual({ confirm_name: 'Acme Hire', note: null });
  });
});
