import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import englishCatalog from '../locales/en.json' with { type: 'json' };
import vietnameseCatalog from '../locales/vi.json' with { type: 'json' };
import { getLanguage, getLocale, setActiveLanguage } from './locale.js';

const STORAGE_KEY = 'dkat-language';
const LOCALES = { en: 'en-US', vi: 'vi-VN' };
const catalogs = { en: englishCatalog, vi: vietnameseCatalog };
const LanguageContext = createContext(null);
const demoVariantLabels = new Set(['Áo', 'Quần', 'Phụ kiện', 'Đen', 'Trắng', 'Xanh', 'Be', 'Tự nhiên', 'One size']);
const vietnameseByEnglish = new Map();

// Support literal English copy alongside message keys. Prefer the Vietnamese value
// when an entry uses a shared key such as a status code.
for (const [source, english] of Object.entries(englishCatalog)) {
  if (!vietnameseByEnglish.has(english)) {
    vietnameseByEnglish.set(english, vietnameseCatalog[source] ?? source);
  }
}

// Movement notes the backend writes itself (sales/service.py, preorders/services/fulfillment.py) are
// stored in Vietnamese; show them in the active language. Notes typed by users are left untouched.
const SYSTEM_NOTES = [
  [/^Bán đơn (\S+)$/, 'inventory.note.sale'],
  [/^Hoàn đơn (\S+)$/, 'inventory.note.refund'],
  [/^Giao đơn (\S+)$/, 'inventory.note.preorderFulfillment'],
];

export function systemNote(note) {
  if (typeof note !== 'string') return note;
  for (const [pattern, key] of SYSTEM_NOTES) {
    const match = note.match(pattern);
    if (match) return { key, values: { code: match[1] } };
  }
  return note;
}

export function demoVariantLabel(value, t) {
  return demoVariantLabels.has(value) ? t(value) : value;
}

export function translate(value, language = getLanguage(), values) {
  if (value && typeof value === 'object') {
    values = value.values;
    value = value.key;
  }
  if (typeof value !== 'string' || !value.trim()) return value;
  const repaired = repairMojibake(value);
  const vndAmount = repaired.match(/^([\d.]+)(?:,(\d+))?\s*(?:₫|VND)$/);
  if (language === 'en' && vndAmount) {
    const amount = Number(vndAmount[1].replaceAll('.', '') + (vndAmount[2] ? `.${vndAmount[2]}` : ''));
    return new Intl.NumberFormat(LOCALES.en, { style: 'currency', currency: 'VND' }).format(amount);
  }
  const catalog = catalogs[language];
  const fallback = language === 'vi' ? vietnameseByEnglish.get(repaired) ?? repaired : repaired;
  const template = catalog && Object.hasOwn(catalog, repaired) ? catalog[repaired] : fallback;
  return values
    ? template.replace(/\{(\w+)\}/g, (placeholder, name) => Object.hasOwn(values, name) ? String(values[name]) : placeholder)
    : template;
}

// Keep messages in their source form until render so an open notice follows the switch.
export function errorMessage(error, fallback = 'Đã xảy ra sự cố khi xử lý yêu cầu. Vui lòng thử lại.') {
  if (error?.translation) return error.translation;
  const message = typeof error === 'string' ? error : error?.message;
  if (message && (Object.hasOwn(catalogs.en, message) || Object.hasOwn(catalogs.vi, message))) return message;
  const code = error?.code;
  const key = `api.error.${code}`;
  return Object.hasOwn(catalogs.en, key) ? key : fallback;
}

function repairMojibake(value) {
  const windows1252Bytes = new Map(Object.entries({
    '€': 0x80, '‚': 0x82, 'ƒ': 0x83, '„': 0x84, '…': 0x85, '†': 0x86, '‡': 0x87,
    'ˆ': 0x88, '‰': 0x89, 'Š': 0x8a, '‹': 0x8b, 'Œ': 0x8c, 'Ž': 0x8e, '‘': 0x91,
    '’': 0x92, '“': 0x93, '”': 0x94, '•': 0x95, '–': 0x96, '—': 0x97, '˜': 0x98,
    '™': 0x99, 'š': 0x9a, '›': 0x9b, 'œ': 0x9c, 'ž': 0x9e, 'Ÿ': 0x9f,
  }));
  return value.replace(/[ÃÂÄÆáâ][\u0080-\u00bf\u2018-\u201f\u20ac\u2122]{1,2}/g, (chunk) => {
    try {
      const bytes = Uint8Array.from([...chunk], (character) => windows1252Bytes.get(character) ?? character.charCodeAt(0));
      return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch {
      return chunk;
    }
  });
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(getLanguage);
  const setLanguage = (next) => {
    const normalized = next === 'en' ? 'en' : 'vi';
    setActiveLanguage(normalized);
    try { localStorage.setItem(STORAGE_KEY, normalized); } catch { /* storage may be disabled */ }
    setLanguageState(normalized);
  };

  useEffect(() => {
    document.documentElement.lang = language;
    const locale = LOCALES[language];
    document.title = translate('page.title', language);
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = translate('meta.description', language);
    document.documentElement.dataset.locale = locale;
  }, [language]);

  const value = useMemo(() => ({
    language,
    locale: LOCALES[language],
    setLanguage,
    t: (text, values) => translate(text, language, values),
    formatNumber: (number, options) => new Intl.NumberFormat(LOCALES[language], options).format(number),
    formatCurrency: (number, options) => new Intl.NumberFormat(LOCALES[language], { ...options, style: 'currency', currency: 'VND' }).format(number),
    formatDate: (date, options = {}) => new Intl.DateTimeFormat(LOCALES[language], { day: '2-digit', month: '2-digit', year: 'numeric', ...options }).format(date),
    formatDateTime: (date, options = {}) => new Intl.DateTimeFormat(LOCALES[language], { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', ...options }).format(date),
  }), [language]);

  return React.createElement(LanguageContext.Provider, { value }, children);
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error('useLanguage must be used within LanguageProvider');
  return value;
}

export function LanguageSwitcher({ className = '' }) {
  const { language, setLanguage, t } = useLanguage();
  return React.createElement('div', { className: `language-switch ${className}`, role: 'group', 'aria-label': t('Language') },
    ...['en', 'vi'].map((option) => React.createElement('button', {
      key: option,
      type: 'button',
      'aria-pressed': language === option,
      'aria-label': t(`language.${option}`),
      onClick: () => setLanguage(option),
    }, option.toUpperCase())),
  );
}

export { getLocale };
