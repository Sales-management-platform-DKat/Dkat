import React from 'react';
import { useLanguage } from '../i18n/index.js';
import { friendlyMessage } from '../lib/api-errors.js';

// Shared loading / empty / error states so every page looks and behaves the same.

export function LoadingState({ label }) {
  const { t } = useLanguage();
  return <div className="state-block" role="status"><span className="auth-spinner" aria-hidden="true" /><span>{label || t('Đang tải dữ liệu…')}</span></div>;
}

export function EmptyState({ title, description, action, icon = '◇' }) {
  return <div className="empty"><span aria-hidden="true">{icon}</span><h3>{title}</h3>{description && <p>{description}</p>}{action}</div>;
}

export function ErrorState({ error, onRetry }) {
  const { t } = useLanguage();
  return <div className="empty error-block" role="alert"><span aria-hidden="true">!</span><h3>{t('Không tải được dữ liệu')}</h3><p>{friendlyMessage(error)}</p>{onRetry && <button className="btn outline" type="button" onClick={onRetry}>{t('Thử lại')}</button>}</div>;
}

const STATUS = {
  ACTIVE: ['Hoạt động', 'green'], INACTIVE: ['Ngừng hoạt động', 'amber'], LOCKED: ['Đã khóa', 'amber'],
  PENDING: ['Chờ thanh toán', 'amber'], PAID: ['Đã thanh toán', 'green'], CANCELLED: ['Đã hủy', ''],
  REFUNDED: ['Đã hoàn tiền', ''], WAITING_STOCK: ['Chờ hàng', 'amber'], READY: ['Sẵn sàng', 'green'],
  NOTIFIED: ['Đã thông báo', 'green'], FULFILLED: ['Đã nhận hàng', 'green'], EXPIRED: ['Hết hạn', ''],
  UNPAID: ['Chưa thanh toán', 'amber'],
};

export function StatusBadge({ status }) {
  const { t } = useLanguage();
  const [label, tone] = STATUS[status] || [status, ''];
  return <span className={`badge ${tone}`}>{t(label)}</span>;
}
