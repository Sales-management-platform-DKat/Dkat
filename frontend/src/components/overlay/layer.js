let locks = 0;
let previousOverflow = '';

export function lockScroll() {
  if (locks === 0) {
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  locks += 1;
  return () => {
    locks = Math.max(0, locks - 1);
    if (locks === 0) document.body.style.overflow = previousOverflow;
  };
}

const layers = [];
let nextLayerId = 0;

export function acquireLayer() {
  const id = ++nextLayerId;
  layers.push(id);
  const zIndex = 160 + (layers.length - 1) * 12;
  return {
    id,
    zIndex,
    release() {
      const index = layers.indexOf(id);
      if (index !== -1) layers.splice(index, 1);
    },
  };
}

export function isTopLayer(id) {
  return layers.at(-1) === id;
}

export const FOCUSABLE = 'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function focusableElements(root) {
  if (!root) return [];
  return [...root.querySelectorAll(FOCUSABLE)].filter((node) => !node.hasAttribute('disabled') && node.tabIndex !== -1);
}
