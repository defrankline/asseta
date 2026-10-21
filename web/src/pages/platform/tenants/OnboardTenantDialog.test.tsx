import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { tenantService } from '../../../api/services/tenantService';
import type { OnboardResultDto, TenantOnboardIn } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { todayIsoDate } from '../../../utils/dates';
import { OnboardTenantDialog } from './OnboardTenantDialog';

const mocks = vi.hoisted(() => ({
  onboard: vi.fn<typeof tenantService.onboard>(),
}));
const onboard = mocks.onboard;
vi.mock('../../../api/services/tenantService', () => ({
  tenantService: { onboard: mocks.onboard },
}));

const result: OnboardResultDto = {
  owner_email: 'owner@acme.test',
  owner_temporary_password: 'Tmp-Secret-123',
  subscription_id: '44444444-4444-4444-8444-444444444444',
  tenant: {
    id: '55555555-5555-4555-8555-555555555555',
    legal_name: 'Acme Plant Hire Ltd',
    display_name: 'Acme',
    registration_number: null,
    contact_name: 'Jane Doe',
    contact_email: 'jane@acme.test',
    contact_phone: null,
    status: 'ONBOARDING',
    access_state: 'FULL',
    access_state_reason: null,
    verification_status: 'UNVERIFIED',
    created_at: '2026-10-21T08:00:00Z',
    version: 1,
  },
};

const field = (name: RegExp) => screen.getByRole('textbox', { name });
const next = () => screen.getByRole('button', { name: 'Next' });

async function fillToReview(user: ReturnType<typeof userEvent.setup>) {
  await user.type(field(/^Legal name/), 'Acme Plant Hire Ltd');
  await user.type(field(/^Display name/), 'Acme');
  await user.type(field(/^Contact name/), 'Jane Doe');
  await user.type(field(/^Contact email/), 'jane@acme.test');
  await user.click(next());
  // Settings: defaults (Africa/Dar_es_Salaam, TZS, en) are valid.
  expect(await screen.findByRole('combobox', { name: /^Timezone/ })).toHaveValue(
    'Africa/Dar_es_Salaam',
  );
  await user.click(next());
  await user.type(await screen.findByRole('textbox', { name: /^Owner email/ }), 'owner@acme.test');
  await user.type(field(/^First name/), 'Owen');
  await user.type(field(/^Last name/), 'Er');
  await user.click(next());
  await screen.findByRole('textbox', { name: /^Unit price per asset/ });
}

describe('OnboardTenantDialog', () => {
  beforeEach(() => {
    onboard.mockReset();
  });

  it('validates each step before moving on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<OnboardTenantDialog onClose={vi.fn()} onOnboarded={vi.fn()} />);
    await user.click(next());
    expect(await screen.findByText('Legal name is required')).toBeInTheDocument();
    expect(screen.getByText('Contact email is required')).toBeInTheDocument();
    await user.type(field(/^Contact email/), 'not-an-email');
    await user.click(next());
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: /^Timezone/ })).not.toBeInTheDocument();
  });

  it('blocks invalid commercial terms, reviews and submits the contract payload', async () => {
    const user = userEvent.setup();
    const onOnboarded = vi.fn();
    onboard.mockResolvedValue(result);
    renderWithProviders(<OnboardTenantDialog onClose={vi.fn()} onOnboarded={onOnboarded} />);
    await fillToReview(user);

    await user.click(next());
    expect(await screen.findByText('Unit price is required')).toBeInTheDocument();
    const minAssets = field(/^Minimum billable assets/);
    await user.clear(minAssets);
    await user.type(minAssets, '0');
    await user.type(field(/^Unit price per asset/), '25000.505');
    await user.click(next());
    expect(
      await screen.findByText('Minimum billable assets must be at least 1'),
    ).toBeInTheDocument();
    await user.clear(minAssets);
    await user.type(minAssets, '3');
    await user.type(field(/^Tax name/), 'VAT');
    const tax = field(/^Tax %/);
    await user.clear(tax);
    await user.type(tax, '18');
    await user.click(next());

    const dialog = screen.getByRole('dialog');
    expect(await within(dialog).findByText('TZS 25,000.51')).toBeInTheDocument();
    expect(within(dialog).getByText('VAT 18%')).toBeInTheDocument();
    expect(within(dialog).getByText('Acme Plant Hire Ltd')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Onboard tenant' }));

    await waitFor(() => {
      expect(onboard).toHaveBeenCalledTimes(1);
    });
    const [payload, key] = onboard.mock.calls[0] ?? [];
    const expected: TenantOnboardIn = {
      legal_name: 'Acme Plant Hire Ltd',
      display_name: 'Acme',
      registration_number: null,
      contact_name: 'Jane Doe',
      contact_email: 'jane@acme.test',
      contact_phone: null,
      timezone: 'Africa/Dar_es_Salaam',
      currency: 'TZS',
      locale: 'en',
      owner: { email: 'owner@acme.test', first_name: 'Owen', last_name: 'Er' },
      subscription: {
        start_date: todayIsoDate(),
        trial_days: 0,
        payment_terms_days: 14,
        rate: {
          currency: 'TZS',
          cadence: 'MONTHLY',
          unit_price: '25000.505',
          minimum_billable_assets: 3,
          discount_percent: '0',
          tax_name: 'VAT',
          tax_rate_percent: '18',
          mid_cycle_add: 'PRORATE_DAILY',
          mid_cycle_remove: 'PRORATE_CREDIT',
          rounding_mode: 'HALF_UP',
        },
      },
    };
    expect(payload).toEqual(expected);
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
    expect(onOnboarded).toHaveBeenCalledWith(result);
  });

  it('maps server field errors onto nested form fields', async () => {
    const user = userEvent.setup();
    onboard.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'VALIDATION_FAILED',
        message: 'Request validation failed',
        correlationId: 'corr-1',
        details: [{ field: 'owner.email', issue: 'Owner email already exists' }],
      }),
    );
    renderWithProviders(<OnboardTenantDialog onClose={vi.fn()} onOnboarded={vi.fn()} />);
    await fillToReview(user);
    await user.type(field(/^Unit price per asset/), '100');
    await user.click(next());
    await user.click(await screen.findByRole('button', { name: 'Onboard tenant' }));
    expect(await screen.findByText('Request validation failed (ref corr-1)')).toBeInTheDocument();
    // Back to the Owner step: the server issue is attached to the field.
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByText('Owner email already exists')).toBeInTheDocument();
  });
});
