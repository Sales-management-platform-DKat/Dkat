import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import englishCatalog from '../locales/en.json' with { type: 'json' };
import vietnameseCatalog from '../locales/vi.json' with { type: 'json' };
import { getLanguage, getLocale, setActiveLanguage } from './locale.js';

const STORAGE_KEY = 'dkat-language';
const LOCALES = { en: 'en-US', vi: 'vi-VN' };
const catalogs = { en: englishCatalog, vi: vietnameseCatalog };
const LanguageContext = createContext(null);

export function translate(value, language = getLanguage()) {
  if (typeof value !== 'string' || !value.trim()) return value;
  const repaired = repairMojibake(value);
  if (language === 'vi') {
    if (catalogs.vi?.[repaired]) return catalogs.vi[repaired];
    // The catalogs also contain Vietnamese-source -> English entries. Reverse
    // those so literal English UI copy is localized even when it was not
    // written as an explicit translation key in the component.
    const sourceVietnamese = Object.entries(catalogs.en).find(([, english]) => english === repaired)?.[0];
    return sourceVietnamese || repaired;
  }
  const vndAmount = repaired.match(/^([\d.]+)(?:,(\d+))?\s*(?:₫|VND)$/);
  if (vndAmount) {
    const amount = Number(vndAmount[1].replaceAll('.', '') + (vndAmount[2] ? `.${vndAmount[2]}` : ''));
    return new Intl.NumberFormat(LOCALES.en, { style: 'currency', currency: 'VND' }).format(amount);
  }
  return catalogs[language]?.[repaired] || catalogs[language]?.[value] || repaired;
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

// JSX is created through React.createElement in this legacy Vite app. Translating
// host-node text and accessible labels here keeps the existing screens intact
// while routing all user-facing copy through the locale catalogs.
if (!React.createElement.__dkatI18n) {
  const originalCreateElement = React.createElement;
  const translateChild = (child) => {
    if (Array.isArray(child)) return child.map(translateChild);
    return typeof child === 'string' ? translate(child) : child;
  };
  const translatedCreateElement = function (type, props, ...children) {
    if (children.length) children = children.map(translateChild);
    if (typeof type === 'string') {
      if (props) {
        const nextProps = { ...props };
        ['aria-label', 'title', 'placeholder', 'alt'].forEach((attribute) => {
          if (typeof nextProps[attribute] === 'string') nextProps[attribute] = translate(nextProps[attribute]);
        });
        props = nextProps;
      }
    }
    return originalCreateElement.call(this, type, props, ...children);
  };
  translatedCreateElement.__dkatI18n = true;
  React.createElement = translatedCreateElement;
}

if (typeof window !== 'undefined' && !window.__dkatConfirmI18n) {
  const nativeConfirm = window.confirm.bind(window);
  window.confirm = (message) => nativeConfirm(translate(String(message)));
  window.__dkatConfirmI18n = true;
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(getLanguage);
  setActiveLanguage(language);
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
    t: (text) => translate(text, language),
    formatNumber: (number, options) => new Intl.NumberFormat(LOCALES[language], options).format(number),
    formatCurrency: (number) => new Intl.NumberFormat(LOCALES[language], { style: 'currency', currency: 'VND' }).format(number),
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
  const { language, setLanguage } = useLanguage();
  return React.createElement('div', { className: `language-switch ${className}`, role: 'group', 'aria-label': translate('Language', language) },
    ...['en', 'vi'].map((option) => React.createElement('button', {
      key: option,
      type: 'button',
      lang: option,
      'aria-pressed': language === option,
      'aria-label': option === 'en' ? 'English' : 'Tiếng Việt',
      onClick: () => setLanguage(option),
    }, option.toUpperCase())),
  );
}

export { getLocale };
