import Add from '@mui/icons-material/Add';
import { Button } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { PRODUCT_TYPES } from '../../../api/services/commerceSchemas';
import type { ProductDto } from '../../../api/types';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstant } from '../../../utils/dates';
import { CatalogItemDialog } from './CatalogItemDialog';
import {
  CATALOG_ERROR_HINTS,
  catalogItemLabel,
  KIND_EFFECTS,
  KIND_LABELS,
  KIND_OPTIONS,
  KIND_TONES,
  priceSummary,
} from './catalogForm';

type Editing = { kind: 'new' } | { kind: 'edit'; item: ProductDto } | null;

const DEACTIVATE_CONSEQUENCES =
  'It can no longer be added to new invoices. Invoices that already contain it are unchanged.';

/** Platform product catalog: subscription fees, SMS bundles and services, with full lifecycle. */
export function CatalogPage() {
  const service = usePlatformInvoicingService();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformCatalogManage);
  const [kind, setKind] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewed, setViewed] = useState<ProductDto | null>(null);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  const filters = useMemo(
    () => ({
      product_type: kind === '' ? undefined : kind,
      include_inactive: String(showInactive),
    }),
    [kind, showInactive],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) => {
      const k = PRODUCT_TYPES.find((x) => x === q.filters.product_type);
      return service.listProducts(
        {
          page: q.page,
          page_size: q.page_size,
          ...(q.q !== undefined && q.q !== '' ? { q: q.q } : {}),
          ...(k !== undefined ? { product_type: k } : {}),
          ...(q.filters.include_inactive === 'true' ? { include_inactive: true } : {}),
        },
        signal,
      );
    },
    [service],
  );

  const lifecycle = useLifecycleDialog<ProductDto>({
    labelOf: catalogItemLabel,
    noun: 'catalog item',
    consequences: DEACTIVATE_CONSEQUENCES,
    errorHints: CATALOG_ERROR_HINTS,
    deactivate: (i, body, key) =>
      service.deactivateProduct(i.id, { ...body, version: i.version }, key),
    reactivate: (i, body, key) =>
      service.reactivateProduct(i.id, { ...body, version: i.version }, key),
    onDone: (i, k) => {
      notify.success(
        `${catalogItemLabel(i)} ${k === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      setViewed(null);
      reload();
    },
    onReload: reload,
  });

  const actionsFor = (i: ProductDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: i.is_active,
      canEdit: canManage,
      canChangeState: canManage,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewed(i);
            },
          }),
      onEdit: () => {
        setViewed(null);
        setEditing({ kind: 'edit', item: i });
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', i);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', i);
      },
    });

  const columns: DataColumn<ProductDto>[] = [
    { id: 'code', header: 'Code', render: (i) => <strong>{i.code}</strong> },
    { id: 'name', header: 'Name', render: (i) => i.name },
    {
      id: 'kind',
      header: 'Type',
      render: (i) => (
        <StatusChip
          status={i.product_type}
          tones={KIND_TONES}
          label={KIND_LABELS[i.product_type]}
        />
      ),
    },
    {
      id: 'price',
      header: 'List prices',
      align: 'right',
      render: (i) => priceSummary(i),
    },
    {
      id: 'credits',
      header: 'SMS credits',
      align: 'right',
      render: (i) => (i.sms_credits === null ? '—' : i.sms_credits.toLocaleString('en-US')),
    },
    { id: 'state', header: 'State', render: (i) => <ActiveChip active={i.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (i) => <RowActionsMenu label={catalogItemLabel(i)} actions={actionsFor(i, false)} />,
    },
  ];

  return (
    <>
      <PageHeader
        title="Product catalog"
        subtitle="Items the platform can invoice: subscription fees, SMS bundles and services"
        actions={
          canManage ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setEditing({ kind: 'new' });
              }}
            >
              Add catalog item
            </Button>
          ) : undefined
        }
      />
      <ServerDataTable<ProductDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(i) => i.id}
        filters={filters}
        searchPlaceholder="Search code or name"
        reloadKey={reloadKey}
        emptyTitle="No catalog items"
        isRowMuted={(i) => !i.is_active}
        onRowClick={setViewed}
        toolbar={
          <>
            <StaticSelectFilter
              label="Type"
              value={kind}
              options={KIND_OPTIONS}
              onChange={setKind}
            />
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </>
        }
      />
      {viewed !== null && (
        <DetailsDrawer
          title={catalogItemLabel(viewed)}
          status={<ActiveChip active={viewed.is_active} />}
          actions={<ActionButtons actions={actionsFor(viewed, true)} />}
          onClose={() => {
            setViewed(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Code', value: viewed.code },
              { label: 'Name', value: viewed.name },
              { label: 'Type', value: KIND_LABELS[viewed.product_type] },
              { label: 'List prices', value: priceSummary(viewed) },
              { label: 'Taxable', value: viewed.taxable ? 'Yes' : 'No' },
              {
                label: 'SMS credits per bundle',
                value: viewed.sms_credits === null ? '—' : String(viewed.sms_credits),
              },
              { label: 'When paid', value: KIND_EFFECTS[viewed.product_type] },
              { label: 'Updated', value: formatInstant(viewed.updated_at) },
              { label: 'Description', value: viewed.description ?? '—' },
              { label: 'Version', value: String(viewed.version) },
              {
                label: 'Deactivated',
                value:
                  viewed.deactivated_at === null
                    ? '—'
                    : `${formatInstant(viewed.deactivated_at)} · ${viewed.deactivation_reason ?? ''}`,
              },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <CatalogItemDialog
          {...(editing.kind === 'edit' ? { item: editing.item } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(i) => {
            notify.success(`${catalogItemLabel(i)} saved.`);
            reload();
          }}
          onReload={reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
