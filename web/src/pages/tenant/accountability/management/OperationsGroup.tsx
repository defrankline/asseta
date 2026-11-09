import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { ExcavatorOperationsSectionDto } from '../../../../api/custodyTypes';
import { StaticTable } from '../../../../components/data/StaticTable';
import { hoursText } from '../../hours/hoursDisplay';
import { machineText } from '../../shared/names';
import { EXCEPTION_TYPE_LABELS } from '../../../../components/meter/exceptionText';
import { humanize } from '../../../../utils/text';
import { KpiCard } from '../../dashboard/KpiCard';
import { CountCard, FigureGrid, FigureGroup, HoursCard } from './figures';

const discrepancyLabel = (type: string): string =>
  (EXCEPTION_TYPE_LABELS as Readonly<Record<string, string>>)[type] ?? humanize(type);

/** Guideline section 8, "Excavator Operations". */
export function OperationsGroup({ section: s }: { section: ExcavatorOperationsSectionDto }) {
  return (
    <FigureGroup id="excavator-operations" title="Excavator operations">
      <FigureGrid>
        <HoursCard title="Operating hours" figure={s.operating_hours} />
        <HoursCard title="Hours allocated to customers" figure={s.customer_hours} />
        <HoursCard title="Authorized non-customer hours" figure={s.authorized_non_customer_hours} />
        <HoursCard title="Unexplained engine hours" figure={s.unexplained_hours} />
        <KpiCard
          title="Meter-reading discrepancies"
          value={s.meter_discrepancies.count}
          valueText={String(s.meter_discrepancies.count)}
          to={s.meter_discrepancies.route}
          rows={s.meter_discrepancies.by_type.map((t) => ({
            key: t.type,
            label: discrepancyLabel(t.type),
            value: t.count,
            valueText: String(t.count),
            to: t.route,
          }))}
        />
        <CountCard title="Pending operational reports" figure={s.pending_reports} />
        <CountCard title="Reports returned for changes" figure={s.returned_reports} />
      </FigureGrid>
      <StaticTable
        ariaLabel="Operating hours by excavator"
        rows={s.by_excavator}
        getRowId={(r) => r.machine_id}
        columns={[
          {
            id: 'machine',
            header: 'Operating hours by excavator',
            render: (r) => (
              <Link component={RouterLink} to={r.route}>
                {machineText(r.machine_code, r.machine_name, r.machine_id)}
              </Link>
            ),
          },
          {
            id: 'op',
            header: 'Operating',
            align: 'right',
            render: (r) => hoursText(r.operating_hours),
          },
          {
            id: 'cust',
            header: 'Customer',
            align: 'right',
            render: (r) => hoursText(r.customer_hours),
          },
          {
            id: 'auth',
            header: 'Authorized',
            align: 'right',
            render: (r) => hoursText(r.authorized_hours),
          },
          {
            id: 'unex',
            header: 'Unexplained',
            align: 'right',
            render: (r) => hoursText(r.unexplained_hours),
          },
        ]}
      />
    </FigureGroup>
  );
}
