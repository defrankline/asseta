import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import type { platformMlService } from '../../../api/services/platformMlService';
import type { ModelStatus } from '../../../api/types';
import { page } from '../../../test/financeFixtures';
import { makeModelDetail, MODEL_ID } from '../../../test/mlFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ModelDetailPage } from './ModelDetailPage';
import { allowedActions } from './modelDisplay';

const mocks = vi.hoisted(() => ({
  getModel: vi.fn<typeof platformMlService.getModel>(),
  act: vi.fn<typeof platformMlService.act>(),
  listDrift: vi.fn<typeof platformMlService.listDrift>(),
  listPredictions: vi.fn<typeof platformMlService.listPredictions>(),
  listInferenceAudit: vi.fn<typeof platformMlService.listInferenceAudit>(),
}));
vi.mock('../../../api/services/platformMlService', () => ({ platformMlService: mocks }));

const READ = [P.platformMlRead];
const MANAGE = [P.platformMlRead, P.platformMlManage];

beforeEach(() => {
  mocks.getModel.mockResolvedValue(makeModelDetail());
  mocks.listDrift.mockResolvedValue(page([]));
  mocks.listPredictions.mockResolvedValue(page([]));
  mocks.listInferenceAudit.mockResolvedValue(page([]));
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderPage(permissions: string[]) {
  renderWithProviders(
    <Routes>
      <Route path="/platform/models/:modelId" element={<ModelDetailPage />} />
    </Routes>,
    { permissions, route: `/platform/models/${MODEL_ID}` },
  );
}

const ALL_BUTTONS = [
  'Approve',
  'Deploy in shadow',
  'Deploy active',
  'Roll back',
  'Reject',
  'Retire',
  'Disable',
];

describe('model lifecycle graph', () => {
  it.each<[ModelStatus, string[]]>([
    ['TRAINED', ['Reject', 'Disable']],
    ['EVALUATED', ['Approve', 'Deploy in shadow', 'Deploy active', 'Reject', 'Retire', 'Disable']],
    ['APPROVED', ['Deploy in shadow', 'Deploy active', 'Reject', 'Retire', 'Disable']],
    ['DEPLOYED_SHADOW', ['Approve', 'Deploy active', 'Roll back', 'Retire', 'Disable']],
    ['DEPLOYED_ACTIVE', ['Roll back', 'Retire', 'Disable']],
    ['RETIRED', ['Disable']],
    ['DISABLED', []],
    ['REJECTED', []],
  ])('shows only the actions allowed from %s', async (status, expected) => {
    mocks.getModel.mockResolvedValue(makeModelDetail({ status }));
    renderPage(MANAGE);
    expect(await screen.findByText('Evaluation vs baseline')).toBeInTheDocument();
    for (const label of ALL_BUTTONS) {
      const button = screen.queryByRole('button', { name: label });
      if (expected.includes(label)) expect(button).toBeInTheDocument();
      else expect(button).not.toBeInTheDocument();
    }
    expect(allowedActions(status)).toHaveLength(expected.length);
  });
});

describe('ModelDetailPage', () => {
  it('renders evaluation vs baseline, manifest, history, drift and monitoring', async () => {
    renderPage(READ);
    const evaluation = await screen.findByRole('region', { name: 'Evaluation vs baseline' });
    expect(within(evaluation).getByText('Passed')).toBeInTheDocument();
    expect(within(evaluation).getAllByText('Calibrated')).toHaveLength(2);
    expect(within(evaluation).queryByText('Not calibrated')).not.toBeInTheDocument();
    expect(within(evaluation).getByText(/not probabilities/)).toBeInTheDocument();
    const metrics = within(evaluation).getByRole('table', { name: 'Evaluation metrics' });
    const recall = within(metrics)
      .getByText(/Recall at k/)
      .closest('tr') as HTMLElement;
    expect(within(recall).getByText('0.4')).toBeInTheDocument();
    expect(within(recall).getByText('0.62')).toBeInTheDocument();
    expect(
      within(evaluation).getByText('Recall lift 0.22 meets the 0.05 minimum.'),
    ).toBeInTheDocument();
    const manifest = screen.getByRole('region', { name: 'Training data manifest' });
    expect(within(manifest).getByText('Train rows')).toBeInTheDocument();
    expect(within(manifest).getByText('300')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Lifecycle history' })).toHaveTextContent(
      'Training run summary',
    );
    const drift = screen.getByRole('region', { name: 'Drift' });
    const driftRow = within(drift).getByText('fuel_per_meter_hour').closest('tr') as HTMLElement;
    expect(within(driftRow).getByText('0.31')).toBeInTheDocument();
    expect(within(driftRow).getByText('Drift')).toBeInTheDocument();
    expect(within(drift).getByText('Stable')).toBeInTheDocument();
    expect(mocks.listDrift).toHaveBeenCalledWith(
      MODEL_ID,
      expect.anything(),
      expect.any(AbortSignal),
    );
    const monitoring = screen.getByRole('region', { name: 'Monitoring' });
    expect(within(monitoring).getByText('120 ms')).toBeInTheDocument();
    expect(within(monitoring).getByText('480 ms')).toBeInTheDocument();
    expect(within(monitoring).getByText('Ok: 10 · Error: 1')).toBeInTheDocument();
    expect(within(monitoring).getByText('Shadow (not shown): 90')).toBeInTheDocument();
    expect(within(monitoring).getByText('Last run failed: MLflow unavailable')).toBeInTheDocument();
  });

  it('disables Approve with the reasons when the evaluation did not pass', async () => {
    const base = makeModelDetail({ evaluation_passed: false });
    const evaluation = base.evaluation;
    if (evaluation === null) throw new Error('fixture has an evaluation');
    mocks.getModel.mockResolvedValue({
      ...base,
      evaluation: {
        ...evaluation,
        passed: false,
        reasons: ['Recall lift 0.01 is below the 0.05 minimum.', 'Only 3 machines (need 5).'],
      },
    });
    renderPage(MANAGE);
    const approve = await screen.findByRole('button', { name: 'Approve' });
    expect(approve).toBeDisabled();
    expect(approve).toHaveAccessibleDescription(
      'Approve unavailable. Evaluation did not pass: Recall lift 0.01 is below the 0.05 minimum. Only 3 machines (need 5).',
    );
    // The other lifecycle commands stay available; the primary is the first enabled one.
    expect(screen.getByRole('button', { name: 'Deploy in shadow' })).toBeEnabled();
  });

  it('disables Approve when no evaluation is recorded', async () => {
    mocks.getModel.mockResolvedValue(makeModelDetail({}, { evaluation: null }));
    renderPage(MANAGE);
    const approve = await screen.findByRole('button', { name: 'Approve' });
    expect(approve).toBeDisabled();
    expect(approve).toHaveAccessibleDescription(/No evaluation recorded yet/);
  });

  it('keeps Approve available when the evaluation passed', async () => {
    renderPage(MANAGE);
    const approve = await screen.findByRole('button', { name: 'Approve' });
    expect(approve).toBeEnabled();
    expect(screen.queryByText(/Approve unavailable/)).not.toBeInTheDocument();
  });

  it('sends the reason and lock version with an action', async () => {
    const user = userEvent.setup();
    mocks.act.mockResolvedValue(makeModelDetail({ status: 'APPROVED' }));
    renderPage(MANAGE);
    await user.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
    expect(await within(dialog).findByText('A reason is required')).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Lift is solid');
    await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
    await waitFor(() => {
      expect(mocks.act).toHaveBeenCalledWith(
        MODEL_ID,
        'APPROVE',
        { reason: 'Lift is solid', lock_version: 4 },
        expect.any(String),
      );
    });
  });

  it.each([
    ['EVALUATION_NOT_PASSED', 'Deploy active', /Deploy in shadow to keep observing it/],
    ['APPROVAL_REQUIRED', 'Deploy active', /Approve this version first/],
    ['SYNTHETIC_MODEL', 'Approve', /synthetic demo data/],
  ])('surfaces %s with a plain hint', async (code, button, hint) => {
    const user = userEvent.setup();
    mocks.act.mockRejectedValue(
      new ApiError({ status: 422, code, message: 'Refused', correlationId: null }),
    );
    renderPage(MANAGE);
    await user.click(await screen.findByRole('button', { name: button }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Go ahead');
    await user.click(within(dialog).getByRole('button', { name: button }));
    expect(await within(dialog).findByText(hint)).toBeInTheDocument();
    expect(within(dialog).getByText(new RegExp(code))).toBeInTheDocument();
  });

  it('offers a reload when the version is stale', async () => {
    const user = userEvent.setup();
    mocks.act.mockRejectedValue(
      new ApiError({ status: 409, code: 'STALE_VERSION', message: 'Changed', correlationId: null }),
    );
    renderPage(MANAGE);
    await user.click(await screen.findByRole('button', { name: 'Retire' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Superseded');
    await user.click(within(dialog).getByRole('button', { name: 'Retire' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Reload' }));
    await waitFor(() => {
      expect(mocks.getModel).toHaveBeenCalledTimes(2);
    });
  });

  it('is read-only for auditors', async () => {
    renderPage(READ);
    expect(await screen.findByText('Evaluation vs baseline')).toBeInTheDocument();
    for (const label of ALL_BUTTONS) {
      expect(screen.queryByRole('button', { name: label })).not.toBeInTheDocument();
    }
  });

  it('lists predictions and inference runs filtered by this version', async () => {
    const user = userEvent.setup();
    const detail = makeModelDetail();
    mocks.listPredictions.mockResolvedValue(
      page([
        {
          id: 'p1',
          tenant_id: detail.model.tenant_id,
          model_version_id: MODEL_ID,
          model_name: 'machine_week_anomaly',
          model_version_number: 3,
          deployment_mode: 'SHADOW',
          evaluation_id: null,
          approval_id: null,
          subject_type: 'MACHINE',
          subject_id: 'cdcdcdcd-0000-4000-8000-000000000001',
          as_of: '2026-10-18T21:00:00Z',
          feature_set_hash: 'f',
          feature_snapshot_ids: [],
          data_cutoff: null,
          features_present: 7,
          score: null,
          raw_score: 0.1234,
          calibrated: false,
          baseline_score: null,
          baseline_raw_score: null,
          threshold: '0.98',
          would_surface: false,
          contributions: [],
          explanations: [],
          policy_version: 'v1',
          decision_state: 'SHADOW',
          case_id: null,
          inference_run_id: 'run',
          created_at: '2026-10-19T00:00:00Z',
        },
      ]),
    );
    renderPage(READ);
    const runs = await screen.findByRole('region', { name: 'Predictions and runs' });
    expect(await within(runs).findByText('Uncalibrated raw 0.123')).toBeInTheDocument();
    expect(mocks.listPredictions.mock.lastCall?.[0].filters?.model_version_id).toBe(MODEL_ID);
    await user.click(within(runs).getByRole('tab', { name: 'Inference runs' }));
    await waitFor(() => {
      expect(mocks.listInferenceAudit.mock.lastCall?.[0].filters?.model_version_id).toBe(MODEL_ID);
    });
  });
});
