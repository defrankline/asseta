import { Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto } from '../../../api/types';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { LOOKUP_ERROR_HINTS } from './lookupForms';
import { AreaFormDialog, CategoryFormDialog } from './LookupRecordForms';
import { MachineListPanel } from './MachineListPanel';
import { MasterDataPanel } from './MasterDataPanel';

type TabKey = 'machines' | 'categories' | 'areas';

const LOOKUP_CONSEQUENCES =
  'Machines already using it keep it, but it can no longer be picked for new or edited machines.';

function CategoriesPanel({ canWrite }: { canWrite: boolean }) {
  const load = useCallback(
    (signal: AbortSignal, q: string | undefined, inactive: boolean) =>
      machineService.listCategories(signal, q, inactive),
    [],
  );
  return (
    <MasterDataPanel<CategoryDto>
      noun="machine category"
      searchPlaceholder="Search categories"
      createLabel="New category"
      emptyTitle="Machine categories"
      load={load}
      columns={[
        { id: 'name', header: 'Name', render: (c) => <strong>{c.name}</strong> },
        { id: 'description', header: 'Description', render: (c) => c.description ?? '—' },
      ]}
      labelOf={(c) => c.name}
      detailItems={(c) => [
        { label: 'Name', value: c.name },
        { label: 'Description', value: c.description ?? '—' },
      ]}
      canWrite={canWrite}
      renderForm={(p) => <CategoryFormDialog {...p} />}
      deactivate={(id, body, key) => machineService.deactivateCategory(id, body, key)}
      reactivate={(id, body, key) => machineService.reactivateCategory(id, body, key)}
      errorHints={LOOKUP_ERROR_HINTS}
      consequences={LOOKUP_CONSEQUENCES}
    />
  );
}

function AreasPanel({ canWrite }: { canWrite: boolean }) {
  const load = useCallback(
    (signal: AbortSignal, q: string | undefined, inactive: boolean) =>
      machineService.listAreas(signal, q, inactive),
    [],
  );
  return (
    <MasterDataPanel<AreaDto>
      noun="operating area"
      searchPlaceholder="Search operating areas"
      createLabel="New operating area"
      emptyTitle="Operating areas"
      load={load}
      columns={[
        { id: 'code', header: 'Code', render: (a) => <strong>{a.code}</strong> },
        { id: 'name', header: 'Name', render: (a) => a.name },
      ]}
      labelOf={(a) => `${a.code} · ${a.name}`}
      detailItems={(a) => [
        { label: 'Code', value: a.code },
        { label: 'Name', value: a.name },
      ]}
      canWrite={canWrite}
      renderForm={(p) => <AreaFormDialog {...p} />}
      deactivate={(id, body, key) => machineService.deactivateArea(id, body, key)}
      reactivate={(id, body, key) => machineService.reactivateArea(id, body, key)}
      errorHints={LOOKUP_ERROR_HINTS}
      consequences={LOOKUP_CONSEQUENCES}
    />
  );
}

/** Equipment registry: machines, machine categories and operating areas. */
export function MachinesPage() {
  const canWrite = useCanMutate(PERMISSIONS.tenantMachineWrite);
  const [tab, setTab] = useState<TabKey>('machines');
  return (
    <>
      <PageHeader
        title="Machines"
        subtitle="Equipment registry: individual assets, categories and operating areas"
      />
      <Paper variant="outlined" className="mb-3">
        <Tabs
          value={tab}
          onChange={(_e, v: TabKey) => {
            setTab(v);
          }}
          aria-label="Registry views"
        >
          <Tab value="machines" label="Machines" />
          <Tab value="categories" label="Categories" />
          <Tab value="areas" label="Operating areas" />
        </Tabs>
      </Paper>
      {tab === 'machines' && <MachineListPanel />}
      {tab === 'categories' && <CategoriesPanel canWrite={canWrite} />}
      {tab === 'areas' && <AreasPanel canWrite={canWrite} />}
    </>
  );
}
