import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { platformMlService, type MlLifecycleAction } from '../../../api/services/platformMlService';
import type { MlModelVersionDetailDto, MlModelVersionDto } from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { EntityDetailsLayout } from '../../../components/lifecycle/EntityDetailsLayout';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import {
  ACTION_EFFECTS,
  ACTION_LABELS,
  allowedActions,
  approvalBlockedReason,
  DESTRUCTIVE_ACTIONS,
  MODEL_ERROR_HINTS,
  MODEL_STATUS_LABELS,
  MODEL_STATUS_TONES,
} from './modelDisplay';
import {
  ApprovalsSection,
  EvaluationSection,
  ManifestSection,
  ModelSummarySection,
} from './ModelSections';
import { ModelRunsTabs } from './ModelRunsTabs';
import { DriftSection, MonitoringSection } from './MonitoringSections';

const INACTIVE = new Set(['RETIRED', 'DISABLED', 'REJECTED']);

function ActionDialog({
  model,
  action,
  onClose,
  onDone,
  onReload,
}: {
  model: MlModelVersionDto;
  action: MlLifecycleAction;
  onClose: () => void;
  onDone: () => void;
  onReload: () => void;
}) {
  const label = ACTION_LABELS[action];
  return (
    <LifecycleActionDialog<MlModelVersionDetailDto>
      title={`${label}: ${model.name} v${String(model.version)}`}
      description={ACTION_EFFECTS[action]}
      confirmLabel={label}
      reasonHelp="Recorded in the lifecycle history and audit log."
      errorHints={MODEL_ERROR_HINTS}
      onConfirm={(reason, key) =>
        platformMlService.act(model.id, action, { reason, lock_version: model.lock_version }, key)
      }
      onDone={onDone}
      onClose={onClose}
      onReload={onReload}
    />
  );
}

/**
 * One model version: lifecycle actions allowed from its status (platform.ml.manage), evaluation vs
 * baseline, manifest, lifecycle history, drift, monitoring and its predictions / inference runs.
 */
export function ModelDetailPage() {
  const { modelId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformMlManage);
  const [acting, setActing] = useState<MlLifecycleAction | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => platformMlService.getModel(modelId, signal),
    [modelId],
  );
  const res = useAsyncResource(load);
  const model = res.data?.model ?? null;
  const approveBlocked = approvalBlockedReason(res.data?.evaluation ?? null);
  const actions: RowAction[] =
    model === null || !canManage
      ? []
      : allowedActions(model.status).map((a) => {
          const blocked = a === 'APPROVE' ? approveBlocked : null;
          return {
            key: a,
            label: ACTION_LABELS[a],
            destructive: DESTRUCTIVE_ACTIONS.has(a),
            ...(blocked !== null ? { disabled: true, disabledReason: blocked } : {}),
            onClick: () => {
              setActing(a);
            },
          };
        });
  return (
    <>
      <EntityDetailsLayout
        title={model === null ? 'Model version' : `${model.name} v${String(model.version)}`}
        subtitle={model?.tenant_name ?? 'Model version'}
        back={{ label: 'All models', to: ROUTES.platformModels }}
        inactive={
          model !== null && INACTIVE.has(model.status)
            ? { title: `This version is ${MODEL_STATUS_LABELS[model.status].toLowerCase()}.` }
            : null
        }
        {...(model !== null
          ? {
              status: (
                <StatusChip
                  status={model.status}
                  tones={MODEL_STATUS_TONES}
                  label={MODEL_STATUS_LABELS[model.status]}
                />
              ),
              actions: (
                <ActionButtons
                  actions={actions}
                  primaryKey={actions.find((a) => a.disabled !== true)?.key ?? ''}
                />
              ),
            }
          : {})}
      >
        <AsyncContent
          resource={res}
          errorTitle="Could not load the model version"
          loadingLabel="Loading model version"
        >
          {(detail) => (
            <Box className="flex flex-col gap-6">
              <ModelSummarySection m={detail.model} timeZone={timeZone} />
              <EvaluationSection evaluation={detail.evaluation} timeZone={timeZone} />
              <ManifestSection manifest={detail.manifest} />
              <ApprovalsSection approvals={detail.approvals} timeZone={timeZone} />
              <DriftSection
                modelId={detail.model.id}
                drift={detail.drift ?? null}
                timeZone={timeZone}
              />
              <MonitoringSection monitoring={detail.monitoring ?? null} timeZone={timeZone} />
              <ModelRunsTabs modelId={detail.model.id} timeZone={timeZone} />
            </Box>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {model !== null && acting !== null && (
        <ActionDialog
          model={model}
          action={acting}
          onClose={() => {
            setActing(null);
          }}
          onDone={() => {
            notify.success(`${ACTION_LABELS[acting]}: done.`);
            res.reload();
          }}
          onReload={res.reload}
        />
      )}
    </>
  );
}
