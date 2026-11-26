import React, { useMemo, useState } from 'react';
import { useLanguage } from './i18n';
import './business-analytics.css';

const nowDate = () => new Date();
const paidOrder = (order) => order.status === 'PAID';
const preorderTotal = (preorder) => preorder.items.reduce((sum, item) => sum + item.price * item.quantity, 0);

function periodStart(period, now) {
  const start = new Date(now);
  if (period === 'today') start.setHours(0, 0, 0, 0);
  else if (period === '7') start.setDate(start.getDate() - 6);
  else if (period === '30') start.setDate(start.getDate() - 29);
  else if (period === 'month') start.setDate(1);
  else if (period === 'previous-month') { start.setDate(1); start.setMonth(start.getMonth() - 1); }
  else if (period === 'year') { start.setMonth(0, 1); start.setHours(0, 0, 0, 0); }
  else return null;
  if (period === '7' || period === '30') start.setHours(0, 0, 0, 0);
  return start;
}

function inPeriod(value, period, now) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  if (period === 'previous-month') return date.getMonth() === new Date(now.getFullYear(), now.getMonth() - 1, 1).getMonth() && date.getFullYear() === new Date(now.getFullYear(), now.getMonth() - 1, 1).getFullYear();
  const start = periodStart(period, now);
  return !start || date >= start;
}

function EmptyReport({ title, children }) {
  return <div className="analytics-empty"><span aria-hidden="true">⌁</span><b>{title}</b><p>{children}</p></div>;
}

function RevenueChart({ orders, preorders, period }) {
  const { t, locale, formatCurrency } = useLanguage();
  const paid = [...orders.filter(paidOrder).map((item) => ({ paidAt: item.paidAt, total: item.total })), ...preorders.map((item) => ({ paidAt: item.fulfilledAt || item.createdAt, total: preorderTotal(item) }))];
  if (!paid.length) return <EmptyReport title={t('Chưa có dữ liệu doanh thu')}>{t('Khi có giao dịch hoàn tất trong dữ liệu demo, biểu đồ sẽ hiển thị tại đây.')}</EmptyReport>;
  const now = nowDate();
  const dates = paid.map((item) => new Date(item.paidAt)).filter((item) => !Number.isNaN(item.getTime()));
  const buckets = [];
  if (period === 'today') {
    for (let hour = 0; hour <= now.getHours(); hour += 1) buckets.push({ date: new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour), key: `h-${hour}`, label: `${hour}:00` });
  } else if (period === 'year') {
    for (let month = 0; month < 12; month += 1) buckets.push({ date: new Date(now.getFullYear(), month, 1), key: `m-${now.getFullYear()}-${month}`, label: new Intl.DateTimeFormat(locale, { month: 'short' }).format(new Date(now.getFullYear(), month, 1)) });
  } else if (period === 'all') {
    const first = dates.reduce((min, date) => date < min ? date : min, dates[0]);
    const start = new Date(first.getFullYear(), first.getMonth(), 1);
    const count = (now.getFullYear() - start.getFullYear()) * 12 + now.getMonth() - start.getMonth() + 1;
    for (let index = 0; index < count; index += 1) { const date = new Date(start.getFullYear(), start.getMonth() + index, 1); buckets.push({ date, key: `m-${date.getFullYear()}-${date.getMonth()}`, label: new Intl.DateTimeFormat(locale, { month: 'short', year: '2-digit' }).format(date) }); }
  } else {
    let firstDay;
    let dayCount;
    if (period === 'previous-month') { firstDay = new Date(now.getFullYear(), now.getMonth() - 1, 1); dayCount = new Date(now.getFullYear(), now.getMonth(), 0).getDate(); }
    else if (period === 'month') { firstDay = new Date(now.getFullYear(), now.getMonth(), 1); dayCount = now.getDate(); }
    else { dayCount = period === 'today' ? 1 : Number(period); firstDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() - dayCount + 1); }
    for (let index = 0; index < dayCount; index += 1) { const date = new Date(firstDay); date.setDate(firstDay.getDate() + index); buckets.push({ date, key: `d-${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`, label: dayCount > 10 ? String(date.getDate()) : new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(date) }); }
  }
  const bucketKey = (date) => period === 'today' ? `h-${date.getHours()}` : period === 'year' || period === 'all' ? `m-${date.getFullYear()}-${date.getMonth()}` : `d-${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  const totals = new Map();
  for (const order of paid) { const date = new Date(order.paidAt); if (!Number.isNaN(date.getTime())) totals.set(bucketKey(date), (totals.get(bucketKey(date)) || 0) + order.total); }
  const points = buckets.map((bucket) => ({ ...bucket, amount: totals.get(bucket.key) || 0 }));
  const max = Math.max(...points.map((item) => item.amount), 1);
  return <div className="analytics-chart" role="img" aria-label={t('Doanh thu demo trong khoảng thời gian đã chọn')}>
    <div className="analytics-chart-axis"><span>{formatCurrency(max)}</span><span>{formatCurrency(Math.round(max / 2))}</span><span>{formatCurrency(0)}</span></div>
    <div className="analytics-chart-bars">{points.map((item) => <div className="analytics-chart-column" key={item.key} title={`${item.date.toLocaleDateString(locale)}: ${formatCurrency(item.amount)}`}><span className={item.amount ? 'has-value' : ''} style={{ height: `${Math.max(item.amount ? 5 : 0, item.amount / max * 100)}%` }} /><small>{item.label}</small></div>)}</div>
  </div>;
}

export default function BusinessAnalytics({ state, branch, role, isDemo }) {
  const { t, locale, formatCurrency, formatNumber } = useLanguage();
  const [period, setPeriod] = useState('30');
  const [rankBy, setRankBy] = useState('quantity');
  const now = nowDate();
  const scopedBranches = role === 'OWNER' ? state.branches : state.branches.filter((item) => item.id === branch);
  const filteredOrders = useMemo(() => state.orders.filter((item) => inPeriod(item.paidAt, period, now) && (!branch || item.branch === branch)), [state.orders, period, branch]);
  const filteredPreorders = useMemo(() => state.preorders.filter((item) => inPeriod(item.createdAt, period, now) && (!branch || item.branch === branch)), [state.preorders, period, branch]);
  if (!isDemo) return <EmptyReport title={t('Báo cáo chưa được kết nối')}>{t('API hiện tại chỉ cung cấp xác thực tài khoản. Báo cáo kinh doanh chưa có nguồn dữ liệu thật; nội dung demo được ẩn khi dùng tài khoản cửa hàng.')}</EmptyReport>;

  const sales = filteredOrders.filter(paidOrder);
  const completedPreorders = state.preorders.filter((item) => item.status === 'FULFILLED' && item.payment === 'PAID' && inPeriod(item.fulfilledAt || item.createdAt, period, now) && (!branch || item.branch === branch));
  const collectedPreorders = state.preorders.filter((item) => item.payment === 'PAID' && item.status !== 'CANCELLED' && inPeriod(item.paidAt || item.createdAt, period, now) && (!branch || item.branch === branch));
  const revenue = sales.reduce((sum, item) => sum + item.total, 0) + completedPreorders.reduce((sum, item) => sum + preorderTotal(item), 0);
  const collected = sales.reduce((sum, item) => sum + item.total, 0) + collectedPreorders.reduce((sum, item) => sum + preorderTotal(item), 0);
  const completedCount = sales.length + completedPreorders.length;
  const orderCount = filteredOrders.length + filteredPreorders.length;
  const processingCount = filteredOrders.filter((item) => !['PAID', 'CANCELLED', 'REFUNDED'].includes(item.status)).length + filteredPreorders.filter((item) => !['FULFILLED', 'CANCELLED'].includes(item.status)).length;
  const cancelledCount = filteredOrders.filter((item) => ['CANCELLED', 'REFUNDED'].includes(item.status)).length + filteredPreorders.filter((item) => item.status === 'CANCELLED').length;
  const unitsSold = sales.reduce((sum, order) => sum + order.items.reduce((n, item) => n + item.quantity, 0), 0) + completedPreorders.reduce((sum, order) => sum + order.items.reduce((n, item) => n + item.quantity, 0), 0);
  const pendingPreorders = filteredPreorders.filter((item) => !['FULFILLED', 'CANCELLED'].includes(item.status));
  const pendingValue = pendingPreorders.reduce((sum, item) => sum + preorderTotal(item), 0);
  const metrics = [['Doanh thu ghi nhận', formatCurrency(revenue), 'Đơn đã trả và đặt trước đã hoàn tất'], ['Tiền đã thu', formatCurrency(collected), 'Gồm khoản đã thanh toán cho đặt trước'], ['Tổng đơn', orderCount, 'Đơn bán và yêu cầu đặt trước'], ['Đơn hoàn tất', completedCount, 'Đơn POS đã trả và đặt trước đã giao'], ['Đang xử lý', processingCount, 'Đơn chưa hoàn tất hoặc chưa hủy'], ['Giá trị TB/đơn', completedCount ? formatCurrency(Math.round(revenue / completedCount)) : '—', 'Trên đơn đã hoàn tất'], ['Sản phẩm đã bán', unitsSold, 'Không gồm đặt trước chưa giao'], ['Đặt trước chờ xử lý', formatCurrency(pendingValue), { key: 'reports.pendingHelp', values: { count: formatNumber(pendingPreorders.length) } }]];

  const productMap = new Map();
  for (const order of [...sales, ...completedPreorders]) for (const item of order.items) {
    const current = productMap.get(item.variant) || { id: item.variant, name: item.name, sku: item.sku, quantity: 0, revenue: 0 };
    current.quantity += item.quantity;
    current.revenue += item.price * item.quantity;
    productMap.set(item.variant, current);
  }
  const topProducts = [...productMap.values()].sort((a, b) => rankBy === 'quantity' ? b.quantity - a.quantity : b.revenue - a.revenue);

  const groupedByDate = new Map();
  for (const order of filteredOrders) {
    const date = new Date(order.paidAt);
    if (Number.isNaN(date.getTime())) continue;
    const key = date.toLocaleDateString('vi-VN');
    const row = groupedByDate.get(key) || { date, total: 0, orders: 0, completed: 0, processing: 0, cancelled: 0, preorders: 0 };
    row.orders += 1;
    if (paidOrder(order)) { row.completed += 1; row.total += order.total; }
    else if (['CANCELLED', 'REFUNDED'].includes(order.status)) row.cancelled += 1;
    else row.processing += 1;
    groupedByDate.set(key, row);
  }
  for (const item of filteredPreorders) {
    const date = new Date(item.createdAt);
    const key = date.toLocaleDateString('vi-VN');
    const row = groupedByDate.get(key) || { date, total: 0, orders: 0, completed: 0, processing: 0, cancelled: 0, preorders: 0 };
    row.orders += 1;
    row.preorders += 1;
    if (item.status === 'FULFILLED' && item.payment === 'PAID') { row.completed += 1; row.total += preorderTotal(item); }
    else if (item.status === 'CANCELLED') row.cancelled += 1;
    else row.processing += 1;
    groupedByDate.set(key, row);
  }
  const orderRows = [...groupedByDate.values()].sort((a, b) => b.date - a.date);

  const branches = scopedBranches.map((item) => {
    const branchSales = state.orders.filter((order) => order.branch === item.id && inPeriod(order.paidAt, period, now) && paidOrder(order));
    const branchPreorders = state.preorders.filter((order) => order.branch === item.id && inPeriod(order.createdAt, period, now));
    const branchCompletedPreorders = state.preorders.filter((order) => order.branch === item.id && order.status === 'FULFILLED' && order.payment === 'PAID' && inPeriod(order.fulfilledAt || order.createdAt, period, now));
    const branchCollectedPreorders = state.preorders.filter((order) => order.branch === item.id && order.payment === 'PAID' && order.status !== 'CANCELLED' && inPeriod(order.paidAt || order.createdAt, period, now));
    const amount = branchSales.reduce((sum, order) => sum + order.total, 0) + branchCompletedPreorders.reduce((sum, order) => sum + preorderTotal(order), 0);
    const count = branchSales.length + branchCompletedPreorders.length;
    return { ...item, amount, collected: branchSales.reduce((sum, order) => sum + order.total, 0) + branchCollectedPreorders.reduce((sum, order) => sum + preorderTotal(order), 0), count, aov: count ? amount / count : 0 };
  });
  const branchTotal = branches.reduce((sum, item) => sum + item.amount, 0);

  return <div className="business-analytics">
    <div className="analytics-demo-notice"><b>{t('BÁO CÁO DEMO')}</b><span>{t('Được tính từ dữ liệu cục bộ trong trình duyệt. Không phải báo cáo máy chủ.')}</span></div>
    <div className="analytics-toolbar"><label>{t('Khoảng thời gian')}<select value={period} onChange={(event) => setPeriod(event.target.value)}><option value="today">{t('Hôm nay')}</option><option value="7">{t('7 ngày gần nhất')}</option><option value="30">{t('30 ngày gần nhất')}</option><option value="month">{t('Tháng này')}</option><option value="previous-month">{t('Tháng trước')}</option><option value="year">{t('Năm nay')}</option><option value="all">{t('Toàn bộ dữ liệu demo')}</option></select></label><span>{t('Phạm vi:') + ' '}{role === 'OWNER' ? t('Toàn hệ thống demo') : state.branches.find((item) => item.id === branch)?.name || t('Chi nhánh đang chọn')}</span></div>
    <section className="analytics-kpis" aria-label={t('Chỉ số kinh doanh')}>{metrics.map(([label, value, help]) => <article className="analytics-kpi" key={label}><span>{t(label)}</span><strong>{typeof value === 'number' ? formatNumber(value) : value}</strong><small>{t(help)}</small></article>)}</section>
    <section className="analytics-panel"><div className="analytics-section-head"><div><h2>{t('Doanh thu theo thời gian')}</h2><p>{t('Chỉ tính đơn đã thanh toán và đặt trước đã hoàn tất.')}</p></div><span className="analytics-badge">{t('Dữ liệu demo')}</span></div><RevenueChart orders={filteredOrders} preorders={completedPreorders} period={period} /></section>
    <section className="analytics-panel"><div className="analytics-section-head"><div><h2>{t('Sản phẩm bán chạy')}</h2><p>{t('Không tính đơn đặt trước chưa giao.')}</p></div><label>{t('Xếp theo')}<select value={rankBy} onChange={(event) => setRankBy(event.target.value)}><option value="quantity">{t('Số lượng')}</option><option value="revenue">{t('Doanh thu')}</option></select></label></div>{topProducts.length ? <div className="analytics-table-wrap"><table><thead><tr><th>#</th><th>{t('Sản phẩm')}</th><th>SKU</th><th>{t('Số lượng')}</th><th>{t('Doanh thu')}</th></tr></thead><tbody>{topProducts.map((item, index) => <tr key={item.id}><td>{index + 1}</td><td>{item.name}</td><td>{item.sku}</td><td>{item.quantity}</td><td>{formatCurrency(item.revenue)}</td></tr>)}</tbody></table></div> : <EmptyReport title={t('Chưa có sản phẩm bán')}>{t('Không có đơn đã thanh toán hoặc đặt trước đã giao trong khoảng này.')}</EmptyReport>}</section>
    <section className="analytics-panel"><div className="analytics-section-head"><div><h2>{t('Thống kê đơn hàng')}</h2><p>{t('Số liệu được nhóm theo ngày tạo giao dịch và yêu cầu đặt trước.')}</p></div></div>{orderRows.length ? <div className="analytics-table-wrap"><table><thead><tr><th>{t('Thời gian')}</th><th>{t('Tổng đơn')}</th><th>{t('Hoàn tất')}</th><th>{t('Đang xử lý')}</th><th>{t('Đã hủy')}</th><th>{t('Đặt trước')}</th><th>{t('Giá trị ghi nhận')}</th></tr></thead><tbody>{orderRows.map((item) => <tr key={item.date.toISOString()}><td>{item.date.toLocaleDateString(locale)}</td><td>{item.orders}</td><td>{item.completed}</td><td>{item.processing}</td><td>{item.cancelled}</td><td>{item.preorders}</td><td>{formatCurrency(item.total)}</td></tr>)}</tbody><tfoot><tr><th>{t('Tổng')}</th><th>{orderRows.reduce((sum, item) => sum + item.orders, 0)}</th><th>{orderRows.reduce((sum, item) => sum + item.completed, 0)}</th><th>{orderRows.reduce((sum, item) => sum + item.processing, 0)}</th><th>{orderRows.reduce((sum, item) => sum + item.cancelled, 0)}</th><th>{orderRows.reduce((sum, item) => sum + item.preorders, 0)}</th><th>{formatCurrency(orderRows.reduce((sum, item) => sum + item.total, 0))}</th></tr></tfoot></table></div> : <EmptyReport title={t('Chưa có đơn trong kỳ')}>{t('Đơn hàng và đặt trước sẽ xuất hiện tại đây khi có dữ liệu demo.')}</EmptyReport>}</section>
    {role === 'OWNER' && <section className="analytics-panel"><div className="analytics-section-head"><div><h2>{t('So sánh chi nhánh')}</h2><p>{t('Chủ cửa hàng · dữ liệu cục bộ của bản demo.')}</p></div></div>{branches.length > 1 && branchTotal > 0 ? <><div className="branch-comparison-chart">{branches.map((item) => <div className="branch-comparison-row" key={item.id}><span>{item.name}</span><div><i style={{ width: `${Math.max(item.amount / Math.max(...branches.map((branchItem) => branchItem.amount), 1) * 100, item.amount ? 2 : 0)}%` }} /></div><b>{formatCurrency(item.amount)}</b></div>)}</div><div className="analytics-table-wrap"><table><thead><tr><th>{t('Chi nhánh')}</th><th>{t('Doanh thu')}</th><th>{t('Tiền đã thu')}</th><th>{t('Đơn hoàn tất')}</th><th>{t('Giá trị TB')}</th><th>{t('Tỷ trọng')}</th></tr></thead><tbody>{branches.map((item) => <tr key={item.id}><td>{item.name}</td><td>{formatCurrency(item.amount)}</td><td>{formatCurrency(item.collected)}</td><td>{item.count}</td><td>{formatCurrency(item.aov)}</td><td>{branchTotal ? formatNumber(item.amount / branchTotal,{style:'percent', minimumFractionDigits:1, maximumFractionDigits:1}) : '—'}</td></tr>)}</tbody></table></div></> : <EmptyReport title={t('Chưa đủ dữ liệu để so sánh')}>{t('Cần dữ liệu giao dịch tại ít nhất một chi nhánh để hiển thị biểu đồ so sánh.')}</EmptyReport>}</section>}
  </div>;
}
