import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { meterService } from '../../../api/services/meterService';
import { explainException } from '../../../components/meter/exceptionText';
import { EXCEPTION_TYPES } from '../../../api/services/meterSchemas';
import { makeException } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ExceptionDetailDialog } from './ExceptionDetailDialog';
import { NOTE_REQUIRED } from './ReviewExceptionDialog';

const mocks = vi.hoisted(() => ({ review: vi.fn<typeof meterService.reviewException>() }));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { reviewException: mocks.review },
}));

function open(perms: string[], onReviewed = vi.fn()) {
  renderWithProviders(
    <ExceptionDetailDialog
      exception={makeException()}
      machineName="EX-01 · Excavator"
      timeZone="UTC"
      onClose={vi.fn()}
      onReviewed={onReviewed}
    />,
    { tenantPermissions: perms },
  );
}

describe('ExceptionDetailDialog', () => {
  it('renders labelled evidence with a neutral explanation', () => {
    open(['tenant.meter.read']);
    expect(
      screen.getByText(
        'Phone fix 412.3 m from the machine tracker position at the same time (offset 10 s); allowed 162 m.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Distance phone ↔ tracker (m)')).toBeInTheDocument();
    expect(screen.getByText('Allowed distance (m)')).toBeInTheDocument();
    expect(screen.getByText('Requires review')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Review' })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fraud|guilty|cheat|theft/i);
  });

  it('requires a note before recording the review', async () => {
    const user = userEvent.setup();
    const reviewed = makeException({ status: 'EXPLAINED', review_note: 'Tracker was in the yard' });
    mocks.review.mockResolvedValue(reviewed);
    const onReviewed = vi.fn();
    open(['tenant.meter.read', 'tenant.meter.review'], onReviewed);
    await user.click(screen.getByRole('button', { name: 'Review' }));
    await user.click(await screen.findByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: /^Explained/ }));
    await user.click(screen.getByRole('button', { name: 'Record review' }));
    expect(await screen.findByText(NOTE_REQUIRED)).toBeInTheDocument();
    expect(mocks.review).not.toHaveBeenCalled();
    await user.type(
      screen.getByRole('textbox', { name: /Review note/ }),
      'Tracker was in the yard',
    );
    await user.click(screen.getByRole('button', { name: 'Record review' }));
    await waitFor(() => {
      expect(mocks.review).toHaveBeenCalledWith(
        makeException().id,
        { outcome: 'EXPLAINED', note: 'Tracker was in the yard' },
        expect.any(String),
      );
    });
    expect(onReviewed).toHaveBeenCalledWith(reviewed);
    expect(document.body.textContent).not.toMatch(/fraud/i);
  });

  it('explains every exception type without accusatory wording', () => {
    for (const t of EXCEPTION_TYPES) {
      expect(explainException(t, {})).not.toMatch(/fraud|guilty|cheat|theft|tamper/i);
    }
  });
});
