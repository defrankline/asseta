import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { PlatformInvoicingServiceContext } from '../../../api/services/platformInvoicingService';
import { STALE_RECORD_MESSAGE } from '../../../components/lifecycle/LifecycleActionDialog';
import {
  fakePlatformInvoicingService,
  SMS_5K,
  type FakePlatformInvoicingService,
} from '../../../test/fakePlatformInvoicingService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CatalogPage } from './CatalogPage';

let fake: FakePlatformInvoicingService;
const READ = [P.platformCatalogRead];
const MANAGE = [P.platformCatalogRead, P.platformCatalogManage];

function renderCatalog(permissions: string[]) {
  return renderWithProviders(
    <PlatformInvoicingServiceContext.Provider value={fake}>
      <CatalogPage />
    </PlatformInvoicingServiceContext.Provider>,
    { permissions },
  );
}

beforeEach(() => {
  fake = fakePlatformInvoicingService();
});

describe('CatalogPage', () => {
  it('lists products with type and list prices; read-only users get View only', async () => {
    const user = userEvent.setup();
    renderCatalog(READ);
    expect(await screen.findByText('SMS-5K')).toBeInTheDocument();
    expect(screen.getAllByText('SMS bundle').length).toBeGreaterThan(0);
    expect(screen.getByText('TZS 100,000.00')).toBeInTheDocument();
    expect(screen.getByText('Negotiated rate')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add catalog item' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Actions for SMS-5K · SMS bundle 5,000' }));
    expect(screen.getByRole('menuitem', { name: 'View details' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  it('sends product_type and show-inactive filters to the server', async () => {
    const user = userEvent.setup();
    renderCatalog(READ);
    await screen.findByText('SMS-5K');
    await user.click(screen.getByRole('combobox', { name: 'Type' }));
    await user.click(screen.getByRole('option', { name: 'SMS bundle' }));
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(fake.listProducts).toHaveBeenLastCalledWith(
        expect.objectContaining({ product_type: 'SMS_BUNDLE', include_inactive: true }),
        expect.any(AbortSignal),
      );
    });
  });

  it('adds an SMS bundle through the stepper (credits required) with a Review', async () => {
    const user = userEvent.setup();
    renderCatalog(MANAGE);
    await user.click(await screen.findByRole('button', { name: 'Add catalog item' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'sms-20k');
    await user.type(within(dialog).getByRole('textbox', { name: /Name/ }), 'SMS bundle 20,000');
    await user.click(within(dialog).getByRole('combobox', { name: /Type/ }));
    await user.click(screen.getByRole('option', { name: 'SMS bundle' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText('Price is required')).toBeVisible();
    await user.type(within(dialog).getByRole('textbox', { name: /Unit price/ }), '360000');
    await user.click(within(dialog).getByRole('button', { name: 'Add price' }));
    const [, secondPrice] = within(dialog).getAllByRole('textbox', { name: /Unit price/ });
    if (secondPrice === undefined) throw new Error('second price row missing');
    await user.type(secondPrice, '150');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText('One price per currency')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Remove price 2' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(
      await within(dialog).findByText('SMS credits are required for an SMS bundle'),
    ).toBeVisible();
    await user.type(within(dialog).getByRole('textbox', { name: /SMS credits/ }), '20000');
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(await within(dialog).findByText('SMS-20K')).toBeInTheDocument();
    expect(within(dialog).getByText('TZS 360,000.00')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Add item' }));
    await waitFor(() => {
      expect(fake.createProduct).toHaveBeenCalledTimes(1);
    });
    expect(fake.createProduct.mock.calls[0]?.[0]).toEqual({
      code: 'SMS-20K',
      name: 'SMS bundle 20,000',
      product_type: 'SMS_BUNDLE',
      description: null,
      taxable: true,
      prices: { TZS: '360000' },
      sms_credits: 20000,
    });
    expect(await screen.findByText('SMS-20K · SMS bundle 20,000 saved.')).toBeInTheDocument();
  });

  it('edits with the version read, and offers Reload on STALE_VERSION', async () => {
    const user = userEvent.setup();
    fake.store.catalog = fake.store.catalog.map((c) =>
      c.id === SMS_5K.id ? { ...c, version: 9 } : c,
    );
    renderCatalog(MANAGE);
    await screen.findByText('SMS-5K');
    // Someone else edits after the list was read.
    fake.store.catalog = fake.store.catalog.map((c) =>
      c.id === SMS_5K.id ? { ...c, version: 10 } : c,
    );
    await user.click(screen.getByRole('button', { name: 'Actions for SMS-5K · SMS bundle 5,000' }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('textbox', { name: /Code/ })).toBeDisabled();
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByText(STALE_RECORD_MESSAGE)).toBeInTheDocument();
    expect(fake.updateProduct.mock.calls[0]?.[1]).toMatchObject({ version: 9 });
  });

  it('deactivates only with a reason and sends the version', async () => {
    const user = userEvent.setup();
    renderCatalog(MANAGE);
    await user.click(
      await screen.findByRole('button', { name: 'Actions for SMS-5K · SMS bundle 5,000' }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    expect(screen.getByText(/can no longer be added to new invoices/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Replaced by SMS-10K');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(fake.deactivateProduct).toHaveBeenCalledWith(
        SMS_5K.id,
        { reason: 'Replaced by SMS-10K', version: 4 },
        expect.any(String),
      );
    });
    expect(await screen.findByText('SMS-5K · SMS bundle 5,000 deactivated.')).toBeInTheDocument();
  });

  it('takes no list price for subscription fees (priced by the negotiated rate)', async () => {
    const user = userEvent.setup();
    renderCatalog(MANAGE);
    await user.click(await screen.findByRole('button', { name: 'Add catalog item' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'SUB');
    await user.type(within(dialog).getByRole('textbox', { name: /Name/ }), 'Monthly fee');
    await user.click(within(dialog).getByRole('combobox', { name: /Type/ }));
    await user.click(screen.getByRole('option', { name: 'Subscription fee' }));
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(within(dialog).getByText(/no list price/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Next' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Add item' }));
    await waitFor(() => {
      expect(fake.createProduct).toHaveBeenCalledWith(
        expect.objectContaining({
          product_type: 'SUBSCRIPTION_FEE',
          prices: {},
          sms_credits: null,
        }),
        expect.any(String),
      );
    });
  });
});
