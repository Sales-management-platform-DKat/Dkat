const STORAGE_KEY = 'dkat-language';

function savedLanguage() {
  try { return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'vi'; }
  catch { return 'vi'; }
}

let activeLanguage = typeof window === 'undefined' ? 'vi' : savedLanguage();

export function getLanguage() { return activeLanguage; }
export function getLocale() { return activeLanguage === 'en' ? 'en-US' : 'vi-VN'; }
export function setActiveLanguage(language) { activeLanguage = language === 'en' ? 'en' : 'vi'; }
