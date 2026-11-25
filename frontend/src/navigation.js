const NAVIGATION = [
  ['dashboard', 'Tổng quan', '◫'],
  ['products', 'Sản phẩm', '◇'],
  ['inventory', 'Kho hàng', '▦'],
  ['pos', 'Bán hàng POS', '⊞'],
  ['orders', 'Đơn bán', '≡'],
  ['preorders', 'Đặt trước', '◷'],
  ['customers', 'Khách hàng', '◎'],
  ['employees', 'Nhân viên', '♙'],
  ['reports', 'Báo cáo', '↗'],
  ['branches', 'Chi nhánh', '⌂'],
  ['notifications', 'Thông báo', '♧'],
  ['settings', 'Cài đặt', '⚙'],
];

export function getNavigationItems({ demoSession, allowed }) {
  return NAVIGATION.filter(([id]) => allowed(id) && (demoSession || id !== 'notifications'));
}
