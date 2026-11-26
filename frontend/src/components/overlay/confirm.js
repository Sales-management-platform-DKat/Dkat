export function confirmAction(options) {
  return new Promise((resolve) => {
    window.dispatchEvent(new CustomEvent('dkat-confirm', { detail: { options, resolve } }));
  });
}
