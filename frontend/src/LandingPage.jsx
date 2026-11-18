import React, { useEffect, useState } from 'react';
import { LanguageSwitcher, getLocale } from './i18n';
import './landing.css';

const featureItems = [
  { id: 'products', number: '01', title: 'Sản phẩm & biến thể', text: 'Tập trung danh mục, SKU, giá bán và các lựa chọn theo từng cửa hàng.', icon: 'box', size: 'feature-wide' },
  { id: 'inventory', number: '02', title: 'Tồn kho chính xác', text: 'Biết hàng đang có, đã giữ và có thể bán ở từng chi nhánh.', icon: 'layers' },
  { id: 'pos', number: '03', title: 'Bán hàng tại quầy', text: 'Tìm sản phẩm, tạo đơn và ghi nhận phương thức thanh toán nhanh gọn.', icon: 'scan' },
  { id: 'orders', number: '04', title: 'Đơn hàng & đặt trước', text: 'Theo sát đơn thường và yêu cầu đặt trước đến khi hoàn tất.', icon: 'receipt' },
  { id: 'customers', number: '05', title: 'Khách hàng', text: 'Lưu thông tin liên hệ và lịch sử mua hàng trong cùng hồ sơ.', icon: 'users' },
  { id: 'branches', number: '06', title: 'Nhiều chi nhánh', text: 'Theo dõi hoạt động từng điểm bán trong một không gian quản trị.', icon: 'branches' },
  { id: 'combos', number: '07', title: 'Combo sản phẩm', text: 'Sắp xếp sản phẩm thành nhóm để đội ngũ dễ tìm và tư vấn.', icon: 'grid' },
  { id: 'reports', number: '08', title: 'Báo cáo kinh doanh', text: 'Xem doanh thu, đơn hàng và các khoản trả trước riêng biệt.', icon: 'chart' },
];

function Icon({ name, size = 20 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  const paths = {
    box: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 8 9 5 9-5M3 8v9l9 5 9-5V8M12 13v9"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    scan: <><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M7 12h10"/><path d="M9 9h6v6H9z"/></>,
    receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-1a6 6 0 0 1 12 0v1H3ZM16 5.5a3 3 0 0 1 0 5.8M18 14a4 4 0 0 1 3 4v2h-3"/></>,
    branches: <><rect x="3" y="4" width="7" height="6" rx="1.5"/><rect x="14" y="14" width="7" height="6" rx="1.5"/><path d="M10 7h3a2 2 0 0 1 2 2v5M15 10v4"/></>,
    grid: <><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></>,
    chart: <><path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 5-6"/><path d="M16 7h3v3"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></>,
    moon: <path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5 8.6 8.6 0 1 0 20.5 15.5Z"/>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
  };
  return <svg {...common}>{paths[name] || paths.box}</svg>;
}

function Metric({ label, value, change, icon }) {
  const count = value === '12,8 triệu' ? { end: 12.8, decimals: 1, suffix: getLocale() === 'en-US' ? ' million' : ' triệu' }
    : value === '186' ? { end: 186, decimals: 0, suffix: '' }
      : value === '08 SKU' ? { end: 8, decimals: 0, suffix: ' SKU', pad: 2 } : null;
  return <div className="lp-metric">
    <span className="lp-metric-icon"><Icon name={icon} size={16} /></span>
    <span className="lp-metric-label">{label}</span>
    <strong {...(count ? { 'data-count': count.end, 'data-count-decimals': count.decimals, 'data-count-suffix': count.suffix, 'data-count-pad': count.pad || 0 } : {})}>{value}</strong>
    <small>{change}</small>
  </div>;
}

function ProductDashboard({ BrandLogo }) {
  const bars = [34, 48, 39, 66, 53, 77, 62, 86, 72, 92, 69, 82];
  return <div className="lp-product" aria-label="Minh họa bảng điều khiển DKat">
    <aside className="lp-product-rail" aria-hidden="true">
      <span className="lp-product-mark"><BrandLogo compact /></span>
      {["grid", "box", "layers", "receipt", "chart"].map((icon, index) => <span className={index === 0 ? 'active' : ''} key={icon}><Icon name={icon} size={17} /></span>)}
      <span className="lp-rail-bottom"><Icon name="users" size={17} /></span>
    </aside>
    <div className="lp-product-main">
      <div className="lp-product-toolbar">
        <div><small>KHÔNG GIAN CỬA HÀNG</small><strong>Tổng quan kinh doanh</strong></div>
        <button className="lp-branch-select" type="button"><Icon name="pin" size={15} /> Tất cả chi nhánh</button>
      </div>
      <div className="lp-product-kicker"><span><i /> BẢN XEM TRƯỚC</span><span>Hôm nay · 08:00–20:00</span></div>
      <div className="lp-metrics">
        <Metric label="Doanh thu hôm nay" value="12,8 triệu" change="↑ 12,4% so với hôm qua" icon="chart" />
        <Metric label="Đơn hoàn tất" value="186" change="24 đơn trong giờ gần nhất" icon="receipt" />
        <Metric label="Sắp hết hàng" value="08 SKU" change="Tại 3 chi nhánh" icon="layers" />
      </div>
      <div className="lp-dashboard-grid">
        <section className="lp-chart-card">
          <div className="lp-card-heading"><div><strong>Doanh thu theo thời gian</strong><small>Diễn biến bán hàng trong ngày</small></div><span>Hôm nay⌄</span></div>
          <div className="lp-chart-summary"><b>12.840.000 ₫</b><small>+12,4%</small></div>
          <div className="lp-chart" aria-label="Biểu đồ doanh thu minh họa">
            <div className="lp-chart-axis"><span>15tr</span><span>10tr</span><span>5tr</span><span>0</span></div>
            <div className="lp-chart-plot">
              <div className="lp-chart-gridlines"><i/><i/><i/><i/></div>
              <svg viewBox="0 0 600 180" preserveAspectRatio="none" role="img" aria-label="Doanh thu tăng dần trong ngày">
                <defs><linearGradient id="lp-area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".24"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>
                <path className="lp-chart-area" d="M0 148 C35 138 45 121 80 128 S125 110 160 119 S205 91 240 105 S285 72 320 88 S365 65 400 78 S450 45 480 63 S540 34 600 24 V180 H0Z" />
                <path className="lp-chart-line" d="M0 148 C35 138 45 121 80 128 S125 110 160 119 S205 91 240 105 S285 72 320 88 S365 65 400 78 S450 45 480 63 S540 34 600 24" />
                <circle cx="480" cy="63" r="5" />
              </svg>
              <div className="lp-chart-labels"><span>08:00</span><span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>18:00</span></div>
            </div>
          </div>
        </section>
        <section className="lp-orders-card">
          <div className="lp-card-heading"><div><strong>Đơn hàng gần đây</strong><small>Danh sách giao dịch mẫu</small></div><span className="lp-live">Demo</span></div>
          <div className="lp-order-row"><span className="lp-order-code">#DH-2048</span><span>Áo thun Basic</span><b>420.000 ₫</b><i className="lp-order-status">Hoàn tất</i></div>
          <div className="lp-order-row"><span className="lp-order-code">#DH-2047</span><span>Túi Canvas</span><b>280.000 ₫</b><i className="lp-order-status">Đang xử lý</i></div>
          <div className="lp-order-row"><span className="lp-order-code">#DH-2046</span><span>Combo mùa hè</span><b>650.000 ₫</b><i className="lp-order-status">Hoàn tất</i></div>
        </section>
      </div>
    </div>
  </div>;
}

function BranchShowcase() {
  const branches = [['Quận 1', 'Đang hoạt động', '8.420.000 ₫', 82], ['Thảo Điền', 'Đang hoạt động', '6.180.000 ₫', 64], ['Bình Thạnh', 'Đang hoạt động', '4.960.000 ₫', 52]];
  return <div className="lp-branch-showcase">
    <div className="lp-branch-top"><div><span className="lp-overline">TỔNG QUAN · DỮ LIỆU MINH HỌA</span><strong>Hoạt động các chi nhánh</strong></div><span className="lp-branch-period">Hôm nay⌄</span></div>
    <div className="lp-branch-total"><small>Tổng doanh thu</small><strong>19.560.000 ₫</strong><span><Icon name="branches" size={15} /> 3 chi nhánh đang hoạt động</span></div>
    <div className="lp-branch-list">{branches.map(([name, status, revenue, amount], index) => <div className="lp-branch-row" key={name}>
      <span className="lp-branch-index">0{index + 1}</span><span className="lp-branch-name"><b>{name}</b><small><i />{status}</small></span>
      <span className="lp-branch-bar"><i style={{ width: `${amount}%` }} /></span><strong>{revenue}</strong>
    </div>)}</div>
    <div className="lp-branch-note"><Icon name="layers" size={16} /><span>Số liệu tồn kho và doanh thu được phân tách theo từng điểm bán.</span></div>
  </div>;
}

function FeatureIllustration({ id }) {
  if (id === 'products') return <div className="lp-feature-illustration lp-illustration-products" aria-hidden="true">
    {[
      ['lp-swatch-blue', 'Áo thun Basic', 'Đen · size M', '320.000 ₫'],
      ['lp-swatch-orange', 'Túi Canvas', 'Be · một cỡ', '280.000 ₫'],
      ['lp-swatch-mint', 'Nón Daily', 'Navy · một cỡ', '190.000 ₫'],
    ].map(([swatch, name, variant, price]) => <div className="lp-catalog-row" key={name}>
      <i className={`lp-catalog-swatch ${swatch}`} />
      <span><b>{name}</b><small>{variant}</small></span>
      <strong>{price}</strong>
    </div>)}
  </div>;

  if (id === 'inventory') return <div className="lp-feature-illustration lp-illustration-inventory" aria-hidden="true">
    <div className="lp-illustration-heading"><span>Tồn kho hiện tại</span><b>3 chi nhánh</b></div>
    <div className="lp-inventory-stats"><span><small>Có thể bán</small><b>248</b></span><span><small>Đã giữ</small><b>36</b></span></div>
    <div className="lp-inventory-track"><i /></div>
    <div className="lp-inventory-foot"><span><i /> Hàng sẵn có</span><span><i /> Đã đặt trước</span></div>
  </div>;

  if (id === 'pos') return <div className="lp-feature-illustration lp-illustration-pos" aria-hidden="true">
    <div className="lp-illustration-heading"><span>Đơn hàng <b>#DH-2084</b></span><Icon name="receipt" size={14} /></div>
    <div className="lp-receipt-row"><span>Áo thun Basic <small>× 2</small></span><b>640.000 ₫</b></div>
    <div className="lp-receipt-row"><span>Túi Canvas <small>× 1</small></span><b>280.000 ₫</b></div>
    <div className="lp-receipt-total"><span>Tổng cộng</span><strong>920.000 ₫</strong></div>
    <span className="lp-pay-button"><Icon name="check" size={13} /> Đã thanh toán</span>
  </div>;

  if (id === 'orders') return <div className="lp-feature-illustration lp-illustration-orders" aria-hidden="true">
    <div className="lp-illustration-heading"><span>Đơn đặt trước</span><b>3 đơn</b></div>
    {[
      ['#DH-2081', 'Chờ xác nhận', 'waiting'],
      ['#DH-2082', 'Đang xử lý', 'processing'],
      ['#DH-2083', 'Đã hoàn thành', 'complete'],
    ].map(([code, label, tone]) => <div className="lp-order-status-row" key={code}>
      <span><i className={`lp-status-dot ${tone}`} />{code}</span><b className={`lp-status-label ${tone}`}>{label}</b>
    </div>)}
  </div>;

  if (id === 'customers') return <div className="lp-feature-illustration lp-illustration-customer" aria-hidden="true">
    <div className="lp-customer-profile"><span className="lp-customer-avatar">AL</span><span><b>Anh Linh</b><small>090 ••• 2184</small></span><Icon name="users" size={15} /></div>
    <div className="lp-customer-stats"><span><small>Tổng số đơn</small><b>12</b></span><span><small>Tổng chi tiêu</small><b>4,8 triệu ₫</b></span></div>
    <div className="lp-customer-note"><i /> Khách hàng thân thiết</div>
  </div>;

  if (id === 'branches') return <div className="lp-feature-illustration lp-illustration-branches" aria-hidden="true">
    {[
      ['01', 'Quận 1', '12,8 tr'],
      ['02', 'Thủ Đức', '8,4 tr'],
      ['03', 'Đà Nẵng', '6,2 tr'],
    ].map(([number, name, revenue]) => <div className="lp-branch-mini-row" key={number}>
      <span className="lp-branch-mini-icon"><Icon name="pin" size={13} /></span><span><b>{name}</b><small><i /> Đang hoạt động</small></span><strong>{revenue}</strong>
    </div>)}
  </div>;

  if (id === 'combos') return <div className="lp-feature-illustration lp-illustration-combo" aria-hidden="true">
    <div className="lp-illustration-heading"><span>Combo cuối tuần</span><b className="lp-save-badge">Tiết kiệm 15%</b></div>
    <div className="lp-combo-items"><span><i className="lp-combo-thumb lp-swatch-blue" />Áo Basic</span><b>+</b><span><i className="lp-combo-thumb lp-swatch-orange" />Túi Canvas</span></div>
    <div className="lp-combo-price"><s>600.000 ₫</s><strong>510.000 ₫</strong></div>
  </div>;

  return <div className="lp-feature-illustration lp-illustration-reports" aria-hidden="true">
    <div className="lp-report-total"><span><small>Doanh thu 7 ngày</small><b>28.640.000 ₫</b></span><strong>↑ 12,4%</strong></div>
    <div className="lp-report-chart">{[34, 52, 41, 68, 48, 82, 100].map((height, index) => <span key={index}><i style={{ height: `${height}%` }} /><small>{['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'][index]}</small></span>)}</div>
  </div>;
}

export default function LandingPage({ BrandLogo, go, startDemo, dark, setDark }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const nodes = document.querySelectorAll('.lp-reveal');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const counterFrames = new Set();
    const animateCounters = (container) => {
      container.querySelectorAll('[data-count]').forEach((node) => {
        if (node.dataset.countStarted) return;
        node.dataset.countStarted = 'true';
        const end = Number(node.dataset.count);
        const decimals = Number(node.dataset.countDecimals || 0);
        const suffix = node.dataset.countSuffix || '';
        const pad = Number(node.dataset.countPad || 0);
        const render = (value) => `${new Intl.NumberFormat(getLocale(), { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value).padStart(pad, '0')}${suffix}`;
        if (reduceMotion) { node.textContent = render(end); return; }
        const start = performance.now();
        let frameId = 0;
        const tick = (now) => {
          counterFrames.delete(frameId);
          const progress = Math.min(1, (now - start) / 1400);
          const eased = 1 - (1 - progress) ** 3;
          node.textContent = render(end * eased);
          if (progress < 1) {
            frameId = requestAnimationFrame(tick);
            counterFrames.add(frameId);
          }
        };
        frameId = requestAnimationFrame(tick);
        counterFrames.add(frameId);
      });
    };
    if (reduceMotion || !('IntersectionObserver' in window)) {
      nodes.forEach((node) => node.classList.add('is-visible'));
      return undefined;
    }
    // Keep the first screen present during hydration; the CSS transition provides its entrance.
    document.querySelectorAll('.lp-hero .lp-reveal').forEach((node) => node.classList.add('is-visible'));
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        if (entry.target.classList.contains('lp-hero-showcase')) animateCounters(entry.target);
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
    nodes.forEach((node) => observer.observe(node));
    const desktop = window.matchMedia('(min-width: 1101px)');
    let frame = 0;
    const updateDashboardParallax = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        const dashboard = document.querySelector('.lp-product');
        if (!dashboard || !desktop.matches || reduceMotion) return;
        const rect = dashboard.getBoundingClientRect();
        const progress = (window.innerHeight * 0.5 - (rect.top + rect.height * 0.5)) / window.innerHeight;
        dashboard.style.setProperty('--lp-parallax-y', `${Math.max(-8, Math.min(8, progress * 12))}px`);
      });
    };
    window.addEventListener('scroll', updateDashboardParallax, { passive: true });
    window.addEventListener('resize', updateDashboardParallax);
    updateDashboardParallax();
    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', updateDashboardParallax);
      window.removeEventListener('resize', updateDashboardParallax);
      if (frame) window.cancelAnimationFrame(frame);
      counterFrames.forEach((counterFrame) => window.cancelAnimationFrame(counterFrame));
    };
  }, []);

  const closeMenu = () => setMenuOpen(false);
  const navLinks = [['overview', 'Tổng quan'], ['features', 'Tính năng'], ['branches', 'Giải pháp'], ['plans', 'Bảng giá'], ['contact', 'Liên hệ']];

  return <div className="dk-landing" id="overview">
    <header className="lp-header lp-enter">
      <span className="lp-brand" onClick={closeMenu}><BrandLogo /></span>
      <nav className={`lp-nav ${menuOpen ? 'is-open' : ''}`} aria-label="Điều hướng chính">
        {navLinks.map(([id, label]) => <a href={`#${id}`} key={id} onClick={closeMenu}>{label}</a>)}
        <a className="lp-mobile-login" href="#/catalog" onClick={closeMenu}>Danh m&#7909;c demo</a>
        <a className="lp-mobile-login" href="#/login" onClick={closeMenu}>Đăng nhập</a>
        <button className="lp-mobile-theme" type="button" onClick={() => { setDark(!dark); closeMenu(); }}><Icon name={dark ? 'sun' : 'moon'} size={18} /> Giao diện {dark ? 'sáng' : 'tối'}</button>
      </nav>
      <div className="lp-header-actions">
        <LanguageSwitcher />
        <button className="lp-theme-toggle" type="button" aria-pressed={dark} aria-label={dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} onClick={() => setDark(!dark)}><Icon name={dark ? 'sun' : 'moon'} size={17} /></button>
        <a className="lp-login" href="#/catalog">Danh m&#7909;c demo</a>
        <a className="lp-login" href="#/login">Đăng nhập</a>
        <button className="lp-button lp-button-primary lp-header-cta" type="button" onClick={() => go('demo')}>Trải nghiệm bản demo <Icon name="arrow" size={17} /></button>
      </div>
      <button className="lp-menu-toggle" type="button" aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'close' : 'menu'} size={22} /></button>
    </header>

    <main>
      <section className="lp-hero">
        <div className="lp-hero-copy lp-reveal">
          <div className="lp-eyebrow"><span className="lp-eyebrow-dot" /> DIGITAL KEY TO ALL <span className="lp-eyebrow-divider" /> QUẢN LÝ BÁN LẺ</div>
          <h1><span className="lp-headline-line">Quản lý <span>kinh doanh.</span></span><em>Đơn giản hơn<br />mỗi ngày.</em></h1>
          <p>DKat gom sản phẩm, đơn hàng, tồn kho và doanh thu vào một nền tảng. Nắm tình hình cửa hàng và chuỗi bán lẻ, dù bạn đang ở bất cứ đâu.</p>
          <div className="lp-hero-actions"><button className="lp-button lp-button-primary" type="button" onClick={() => go('demo')}>Trải nghiệm bản demo <Icon name="arrow" size={18} /></button><a className="lp-button lp-button-secondary" href="#features">Khám phá tính năng</a></div>
          <div className="lp-hero-proof"><span><Icon name="check" size={16} /> Nhiều chi nhánh</span><span><Icon name="check" size={16} /> POS & tồn kho</span><span><Icon name="check" size={16} /> Đặt trước FIFO</span></div>
          <small className="lp-demo-note">Không cần tạo tài khoản · Dữ liệu trải nghiệm là dữ liệu mẫu</small>
        </div>
        <div className="lp-hero-showcase lp-reveal"><ProductDashboard BrandLogo={BrandLogo} /><div className="lp-showcase-caption"><span><i /> GIAO DIỆN QUẢN TRỊ DKAT</span><span>Minh họa sản phẩm</span></div></div>
        <div className="lp-hero-orb lp-hero-orb-one" /><div className="lp-hero-orb lp-hero-orb-two" />
      </section>

      <section className="lp-trust lp-reveal" aria-label="Các hoạt động được quản lý trên DKat">
        <p>Một nơi để vận hành<br /><strong>mọi hoạt động kinh doanh.</strong></p>
        <div className="lp-trust-items"><span><Icon name="box" /> Sản phẩm</span><i /><span><Icon name="layers" /> Tồn kho</span><i /><span><Icon name="scan" /> Bán hàng POS</span><i /><span><Icon name="receipt" /> Đơn đặt trước</span><i /><span><Icon name="chart" /> Báo cáo</span></div>
      </section>

      <section className="lp-values lp-section" id="solutions">
        <div className="lp-section-heading lp-reveal"><span className="lp-overline">TẬP TRUNG VÀO VIỆC QUAN TRỌNG</span><h2>Mọi hoạt động kinh doanh,<br /><em>trong tầm kiểm soát.</em></h2><p>Giảm những thao tác rời rạc để bạn có thêm thời gian phục vụ khách hàng và phát triển cửa hàng.</p></div>
        <div className="lp-value-row lp-reveal">
          <article><span className="lp-value-icon"><Icon name="grid" size={21} /></span><small>01 / MỘT KHÔNG GIAN</small><h3>Quản lý tập trung</h3><p>Sản phẩm, đơn hàng và chi nhánh cùng nằm trong một hệ thống dễ theo dõi.</p></article>
          <article><span className="lp-value-icon"><Icon name="layers" size={21} /></span><small>02 / QUY TRÌNH RÕ RÀNG</small><h3>Vận hành thông minh</h3><p>Biết lượng hàng nào đang có, đã giữ và sẵn sàng để bán tại từng điểm.</p></article>
          <article><span className="lp-value-icon"><Icon name="chart" size={21} /></span><small>03 / SẴN SÀNG MỞ RỘNG</small><h3>Phát triển dễ dàng</h3><p>Bổ sung chi nhánh và phân quyền đội ngũ theo cách cửa hàng đang vận hành.</p></article>
        </div>
      </section>

      <section className="lp-features lp-section" id="features">
        <div className="lp-section-heading lp-section-heading-center lp-reveal"><span className="lp-overline">MỘT NỀN TẢNG, ĐỦ CÔNG CỤ</span><h2>Toàn bộ hoạt động.<br /><em>Kết nối trong DKat.</em></h2><p>Từ lần bán đầu tiên đến quản lý một chuỗi cửa hàng, mọi công cụ ở cùng một nơi.</p></div>
        <div className="lp-bento">{featureItems.map((item) => <article className={`lp-feature lp-reveal`} key={item.id}>
          <div className="lp-feature-head"><span className="lp-feature-icon"><Icon name={item.icon} size={21} /></span><small>{item.number}</small></div><h3>{item.title}</h3><p>{item.text}</p>
          <FeatureIllustration id={item.id} />
        </article>)}</div>
      </section>

      <section className="lp-branches lp-section" id="branches">
        <div className="lp-branch-copy lp-reveal"><span className="lp-overline">ĐIỀU HÀNH CHUỖI CỬA HÀNG</span><h2>Một hệ thống.<br /><em>Nhiều chi nhánh.<br />Một tầm nhìn.</em></h2><p>Chuyển giữa các điểm bán hoặc xem bức tranh tổng thể. Doanh thu, tồn kho và hoạt động của từng chi nhánh luôn được phân tách rõ ràng.</p><ul><li><Icon name="check" /> Theo dõi hiệu quả từng điểm bán</li><li><Icon name="check" /> Quản lý tồn kho theo chi nhánh</li><li><Icon name="check" /> Phân quyền theo vai trò</li></ul><button className="lp-text-link" type="button" onClick={() => startDemo('OWNER', 'branches')}>Xem quản lý chi nhánh trong demo <Icon name="arrow" size={17} /></button></div>
        <div className="lp-branch-visual lp-reveal"><BranchShowcase /></div>
      </section>

      <section className="lp-workflow lp-section" id="workflow">
        <div className="lp-section-heading lp-section-heading-center lp-reveal"><span className="lp-overline">BẮT ĐẦU NHẸ NHÀNG</span><h2>Ba bước để vận hành<br /><em>trên cùng một nền tảng.</em></h2></div>
        <div className="lp-steps lp-reveal">{[['01', 'Tạo không gian DKat', 'Bắt đầu bằng một cửa hàng và mời đội ngũ phù hợp.'], ['02', 'Thiết lập cửa hàng', 'Thêm sản phẩm, chi nhánh và thông tin tồn kho ban đầu.'], ['03', 'Theo dõi hoạt động', 'Quản lý bán hàng, đơn đặt trước và báo cáo mỗi ngày.']].map(([number, title, text], index) => <article key={number}><span className="lp-step-number">{number}</span>{index < 2 && <span className="lp-step-connector" />}<h3>{title}</h3><p>{text}</p></article>)}</div>
      </section>

      <section className="lp-analytics lp-section">
        <div className="lp-analytics-copy lp-reveal"><span className="lp-overline">NHÌN RÕ TRƯỚC KHI QUYẾT ĐỊNH</span><h2>Đọc nhịp kinh doanh<br /><em>qua dữ liệu.</em></h2><p>Nhìn doanh thu, số đơn và hàng bán chạy để hiểu hoạt động cửa hàng đang diễn ra như thế nào.</p><button className="lp-text-link" type="button" onClick={() => startDemo('OWNER', 'reports')}>Khám phá báo cáo <Icon name="arrow" size={17} /></button></div>
        <div className="lp-analytics-card lp-reveal"><div className="lp-analytics-head"><div><small>BÁO CÁO MẪU</small><strong>Hiệu quả kinh doanh</strong></div><span>7 ngày qua⌄</span></div><div className="lp-analytics-total"><div><small>Doanh thu ghi nhận</small><strong>84.620.000 ₫</strong></div><span>Minh họa dữ liệu</span></div><div className="lp-analytics-chart">{[42, 58, 48, 73, 63, 88, 70].map((height, index) => <div key={index}><i style={{ height: `${height}%` }} /><small>{['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'][index]}</small></div>)}</div><div className="lp-analytics-foot"><span><i className="lp-legend-dot" /> Doanh thu</span><span>Đơn bán <b>342</b></span><span>Chi nhánh hiệu quả <b>Quận 1</b></span></div></div>
      </section>

      <section className="lp-faq lp-section">
        <div className="lp-faq-heading lp-reveal"><span className="lp-overline">MINH BẠCH TỪ ĐẦU</span><h2>Rõ ràng để<br /><em>dễ bắt đầu.</em></h2><p>Trải nghiệm giao diện và quy trình trước khi triển khai cho cửa hàng.</p></div>
        <div className="lp-faq-list lp-reveal"><details><summary>Đây có phải là bản dùng thử trực tiếp không?</summary><p>Nút dùng thử mở bản demo với dữ liệu mẫu lưu trên trình duyệt. Bản demo giúp bạn khám phá giao diện và quy trình, không tạo tài khoản thật.</p></details><details><summary>DKat phù hợp với mô hình cửa hàng nào?</summary><p>DKat hướng đến cửa hàng bán lẻ và chuỗi cửa hàng cần quản lý sản phẩm, tồn kho, bán tại quầy và hoạt động nhiều chi nhánh.</p></details><details><summary>DKat có xử lý thanh toán trực tuyến không?</summary><p>Chưa. Trong bản hiện tại, nhân viên ghi nhận phương thức thanh toán sau khi kiểm tra giao dịch thực tế.</p></details></div>
      </section>

      <section className="lp-pricing lp-section lp-reveal" id="plans">
        <div><span className="lp-overline">LỰA CHỌN THEO QUY MÔ</span><h2>Bắt đầu từ nhu cầu<br /><em>của cửa hàng bạn.</em></h2></div>
        <div><p>Thông tin giá chưa được công bố trên trang. Hãy trải nghiệm demo để xem các luồng quản lý phù hợp với cửa hàng của bạn.</p><button className="lp-button lp-button-secondary" type="button" onClick={() => go('demo')}>Trải nghiệm bản demo <Icon name="arrow" size={17} /></button></div>
      </section>

      <section className="lp-cta lp-section lp-reveal" id="contact">
        <div className="lp-cta-glow" /><span className="lp-overline">DIGITAL KEY TO ALL</span><h2>Sẵn sàng nâng cấp<br />cách bạn kinh doanh?</h2><p>Bắt đầu hành trình quản lý kinh doanh thông minh cùng DKat.</p><div className="lp-hero-actions"><button className="lp-button lp-button-light" type="button" onClick={() => go('demo')}>Trải nghiệm bản demo <Icon name="arrow" size={18} /></button><a href="#plans" className="lp-button lp-button-ghost">Tìm hiểu lựa chọn</a></div><small>Không cần tạo tài khoản để trải nghiệm</small>
      </section>
    </main>

    <footer className="lp-footer lp-reveal">
      <div className="lp-footer-brand"><BrandLogo /><p>Digital Key To All.<br />Công cụ rõ ràng cho cửa hàng bán lẻ.</p></div>
      <div className="lp-footer-column"><strong>Khám phá</strong><a href="#features">Tính năng</a><a href="#branches">Quản lý chi nhánh</a><a href="#workflow">Cách bắt đầu</a></div>
      <div className="lp-footer-column"><strong>Tài khoản</strong><a href="#/login">Đăng nhập cửa hàng</a><button type="button" onClick={() => go('demo')}>Trải nghiệm bản demo </button><a href="#/platform-admin">Quản trị hệ thống</a></div>
      <div className="lp-footer-bottom"><span>© {new Date().getFullYear()} DKat · Digital Key To All</span><span>Giao diện trải nghiệm · Không nhận thanh toán thật</span></div>
    </footer>
  </div>;
}
