import React, { useEffect, useMemo, useState } from 'react';
import { errorMessage, useLanguage } from '../../i18n/index.js';
import { getReportSummary, getRevenueReport, getTopProducts } from './api.js';

function vnDate(date) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}

export default function DashboardPage({ branchId }) {
  const { t, formatCurrency, formatDate, formatNumber } = useLanguage();
  const [range, setRange] = useState('30');
  const [data, setData] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [topProducts, setTopProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const filters = useMemo(() => {
    const to = vnDate(new Date());
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - Number(range) + 1);
    return { from: vnDate(fromDate), to, branchId };
  }, [range, branchId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([
      getReportSummary(filters),
      getRevenueReport({ ...filters, granularity: range === '7' ? 'day' : 'week' }),
      getTopProducts({ ...filters, limit: 8 }),
    ]).then(([summary, revenueData, productData]) => {
      if (!active) return;
      setData(summary);
      setRevenue(revenueData);
      setTopProducts(productData?.items || []);
    }).catch((cause) => {
      if (!active) return;
      setData(null);
      setRevenue(null);
      setTopProducts([]);
      setError(errorMessage(cause, 'Không tải được báo cáo dashboard.'));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters, range]);

  const points = revenue?.points || [];
  const maxRevenue = Math.max(1, ...points.map((point) => Number(point.revenue || 0)));
  const dateLabel = (value) => formatDate(new Date(`${value}T00:00:00`));
  const periodLabel = (point) => {
    const week = /^(\d{4})-W(\d{2})$/.exec(point.period);
    if (week) return t('reports.week', { year: week[1], week: Number(week[2]) });
    return /^\d{4}-\d{2}-\d{2}$/.test(point.period) ? dateLabel(point.period) : point.period;
  };
  const metricCards = data ? [
    [t('Tổng doanh thu'), formatCurrency(data.revenue?.value || 0), data.revenue?.change_percent, 'revenue'],
    [t('Tổng số đơn'), formatNumber(data.order_count?.value || 0), data.order_count?.change_percent, 'orders'],
    [t('Giá trị đơn trung bình'), formatCurrency(data.average_order_value?.value || 0), data.average_order_value?.change_percent, 'average'],
    [t('Doanh thu bán tại quầy'), formatCurrency(data.sales_revenue || 0), null, 'sales'],
  ] : [];

  return <div className="live-dashboard">
    <div className="toolbar live-dashboard-toolbar">
      <label className="dashboard-range-label">{t('Khoảng thời gian')}<select value={range} onChange={(event) => setRange(event.target.value)}><option value="7">{t('7 ngày qua')}</option><option value="30">{t('30 ngày qua')}</option><option value="90">{t('90 ngày qua')}</option></select></label>
      <span className="muted small">{dateLabel(filters.from)} — {dateLabel(filters.to)}</span>
    </div>
    {error && <div className="notice error-state" role="alert">{t(error)}</div>}
    {loading ? <section className="panel"><p className="muted" role="status">{t('Đang tải dữ liệu kinh doanh…')}</p></section> : !data ? <section className="panel"><div className="empty"><h3>{t('Chưa có dữ liệu báo cáo')}</h3><p>{t('Kiểm tra quyền truy cập chi nhánh và thử lại.')}</p></div></section> : <>
      <div className="stat-grid live-dashboard-stats">{metricCards.map(([label, value, change, key]) => <article className="stat dashboard-stat" key={key}><small>{label}</small><strong>{value}</strong><span className="dashboard-stat-description">{change == null ? t('Trong khoảng đã chọn') : t('reports.periodChange', { change: formatNumber(change / 100, { style: 'percent', signDisplay: 'exceptZero', maximumFractionDigits: 2 }) })}</span></article>)}</div>
      <div className="dashboard-grid live-dashboard-grid">
        <section className="panel dashboard-chart-panel"><div className="section-title"><div><h3>{t('Doanh thu theo thời gian')}</h3><p className="dashboard-panel-subtitle">{t('Dữ liệu đã thanh toán và đặt trước hoàn tất')}</p></div></div>
          {points.length ? <div className="live-revenue-chart" role="img" aria-label={t('Biểu đồ doanh thu')}>
            {points.map((point) => {
              const label = periodLabel(point);
              return <div className="live-revenue-point" key={point.period} title={`${label}: ${formatCurrency(point.revenue)}`}><span className="live-revenue-bar" style={{ height: `${Math.max(3, Number(point.revenue || 0) / maxRevenue * 100)}%` }} /><small>{label}</small></div>;
            })}
          </div> : <div className="empty"><p>{t('Chưa có doanh thu trong khoảng thời gian này.')}</p></div>}
        </section>
        <section className="panel live-top-products"><div className="section-title"><h3>{t('Sản phẩm bán chạy')}</h3><span className="muted small">{t('Xếp theo doanh thu')}</span></div>
          {topProducts.length ? <div className="table-wrap"><table><thead><tr><th>#</th><th>{t('Sản phẩm')}</th><th>{t('Số lượng')}</th><th>{t('Doanh thu')}</th></tr></thead><tbody>{topProducts.map((item) => <tr key={`${item.sku}-${item.rank}`}><td>{item.rank}</td><td><strong>{item.product_name}</strong><small className="block muted">{item.sku}</small></td><td>{item.quantity}</td><td>{formatCurrency(item.revenue)}</td></tr>)}</tbody></table></div> : <div className="empty"><p>{t('Chưa có dữ liệu sản phẩm bán ra.')}</p></div>}
        </section>
      </div>
    </>}
  </div>;
}
