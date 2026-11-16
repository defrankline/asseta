import { Box, Button, Paper, Tab, Tabs } from '@mui/material';
import { Link as RouterLink, useSearchParams } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { ExpensesTab } from './ExpensesTab';
import { FuelTab } from './FuelTab';

type TabKey = 'expenses' | 'fuel';

/**
 * Expenses & fuel (backend `tenant.expenses` menu); categories are one click away. With fuel switched
 * off for the company (`FUEL` disabled) the page is "Expenses" with no fuel tab at all.
 */
export function ExpensesPage() {
  const timeZone = useDisplayTimeZone();
  const fuelOn = useCapabilityEnabled(CAPABILITY.fuel);
  const [params, setParams] = useSearchParams();
  const tab: TabKey = fuelOn && params.get('tab') === 'fuel' ? 'fuel' : 'expenses';
  return (
    <>
      <PageHeader
        title={fuelOn ? 'Expenses & fuel' : 'Expenses'}
        subtitle={
          fuelOn
            ? 'Field expenses with receipts and GPS, approval limits from the EXPENSE_CAPTURE policy, and the fuel log'
            : 'Field expenses with receipts and GPS, and approval limits from the EXPENSE_CAPTURE policy'
        }
        actions={
          <Button component={RouterLink} to={ROUTES.tenantExpenseCategories} variant="outlined">
            Expense categories
          </Button>
        }
      />
      {!fuelOn ? (
        <ExpensesTab timeZone={timeZone} />
      ) : (
        <Paper variant="outlined">
          <Tabs
            value={tab}
            aria-label="Expenses and fuel"
            onChange={(_e, v: TabKey) => {
              setParams({ tab: v });
            }}
          >
            <Tab value="expenses" label="Expenses" />
            <Tab value="fuel" label="Fuel events" />
          </Tabs>
          <Box className="p-3">
            {tab === 'expenses' ? (
              <ExpensesTab timeZone={timeZone} />
            ) : (
              <FuelTab timeZone={timeZone} />
            )}
          </Box>
        </Paper>
      )}
    </>
  );
}
