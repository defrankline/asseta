import AccountBalanceWalletOutlined from '@mui/icons-material/AccountBalanceWalletOutlined';
import ApartmentOutlined from '@mui/icons-material/ApartmentOutlined';
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import FolderOutlined from '@mui/icons-material/FolderOutlined';
import InsightsOutlined from '@mui/icons-material/InsightsOutlined';
import LocalShippingOutlined from '@mui/icons-material/LocalShippingOutlined';
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined';
import ReportProblemOutlined from '@mui/icons-material/ReportProblemOutlined';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';
import WorkOutlined from '@mui/icons-material/WorkOutlined';
import type { SvgIconComponent } from '@mui/icons-material';

/** Header icon per server menu group key (`<scope>.<section>`); unknown groups get a folder. */
const ICONS: Readonly<Record<string, SvgIconComponent>> = {
  overview: DashboardOutlined,
  operations: WorkOutlined,
  fleet: LocalShippingOutlined,
  finance: AccountBalanceWalletOutlined,
  risk: ReportProblemOutlined,
  admin: SettingsOutlined,
  account: SettingsOutlined,
  tenants: ApartmentOutlined,
  billing: ReceiptLongOutlined,
  intelligence: InsightsOutlined,
};

export function navGroupIcon(groupKey: string): SvgIconComponent {
  const section = groupKey.slice(groupKey.indexOf('.') + 1);
  return ICONS[section] ?? FolderOutlined;
}
