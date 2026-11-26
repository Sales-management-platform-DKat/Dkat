// Same-origin messaging between the POS window and the Customer Display window.
//
// Primary transport: BroadcastChannel. Fallback (older browsers): postMessage
// between the POS window and the popup it opened (window.opener). Only display
// data travels over the channel: product lines and totals. No token, password
// or customer data, nothing in the URL and nothing in localStorage.

export const CHANNEL_NAME = 'dkat-customer-display';
export const WINDOW_NAME = 'dkat-customer-display';
export const DISPLAY_ROUTE = '#/pos/customer-display';
export const HEARTBEAT_MS = 2000;
export const STALE_AFTER_MS = 6500;

function makeTransport(onMessage, getPeer) {
  if (typeof BroadcastChannel === 'function') {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (event) => onMessage(event.data);
    return { kind: 'broadcast', send: (message) => channel.postMessage(message), close: () => channel.close() };
  }
  const listener = (event) => {
    if (event.origin !== window.location.origin || event.data?.channel !== CHANNEL_NAME) return;
    onMessage(event.data);
  };
  window.addEventListener('message', listener);
  return {
    kind: 'postMessage',
    send: (message) => {
      const peer = getPeer();
      if (peer && !peer.closed) peer.postMessage({ ...message, channel: CHANNEL_NAME }, window.location.origin);
    },
    close: () => window.removeEventListener('message', listener),
  };
}

/** POS side: publishes the cart state and tracks whether a display is listening. */
export function createDisplayPublisher({ onConnectionChange } = {}) {
  let popup = null;
  let state = null;
  let lastSeen = 0;
  let connected = false;
  const setConnected = (value) => {
    if (value === connected) return;
    connected = value;
    onConnectionChange?.(value);
  };
  const transport = makeTransport((message) => {
    if (message?.from !== 'display') return;
    lastSeen = Date.now();
    setConnected(true);
    // A display that (re)opens asks for the current state.
    if (message.type === 'hello' && state) transport.send({ from: 'pos', type: 'state', state });
    if (message.type === 'bye') { lastSeen = 0; setConnected(false); }
  }, () => popup);
  const heartbeat = setInterval(() => {
    transport.send({ from: 'pos', type: 'ping' });
    if (connected && Date.now() - lastSeen > STALE_AFTER_MS) setConnected(false);
  }, HEARTBEAT_MS);
  const onUnload = () => transport.send({ from: 'pos', type: 'bye' });
  window.addEventListener('pagehide', onUnload);

  return {
    transport: transport.kind,
    publish(next) {
      state = next;
      transport.send({ from: 'pos', type: 'state', state });
    },
    /** Must run inside a click handler, or the browser may block the popup. */
    open() {
      if (popup && !popup.closed) { popup.focus(); return { ok: true, reused: true }; }
      const url = `${window.location.origin}${window.location.pathname}${DISPLAY_ROUTE}`;
      const features = 'popup=yes,width=1280,height=800,menubar=no,toolbar=no,location=no,status=no';
      popup = window.open(url, WINDOW_NAME, features);
      if (!popup) return { ok: false, blocked: true, url };
      return { ok: true, reused: false };
    },
    isWindowOpen: () => !!popup && !popup.closed,
    isConnected: () => connected,
    destroy() {
      onUnload();
      clearInterval(heartbeat);
      window.removeEventListener('pagehide', onUnload);
      transport.close();
    },
  };
}

/** Display side: receives state only; it can never send sales commands. */
export function createDisplaySubscriber({ onState, onConnectionChange }) {
  let lastSeen = 0;
  let connected = false;
  const setConnected = (value) => {
    if (value === connected) return;
    connected = value;
    onConnectionChange?.(value);
  };
  const transport = makeTransport((message) => {
    if (message?.from !== 'pos') return;
    if (message.type === 'bye') { lastSeen = 0; setConnected(false); onState?.(null); return; }
    lastSeen = Date.now();
    setConnected(true);
    if (message.type === 'state') onState?.(message.state);
    if (message.type === 'ping') transport.send({ from: 'display', type: 'pong' });
  }, () => window.opener);
  transport.send({ from: 'display', type: 'hello' });
  const timer = setInterval(() => {
    if (connected && Date.now() - lastSeen > STALE_AFTER_MS) setConnected(false);
    if (!connected) transport.send({ from: 'display', type: 'hello' });
  }, HEARTBEAT_MS);
  const onUnload = () => transport.send({ from: 'display', type: 'bye' });
  window.addEventListener('pagehide', onUnload);
  return {
    transport: transport.kind,
    destroy() {
      onUnload();
      clearInterval(timer);
      window.removeEventListener('pagehide', onUnload);
      transport.close();
    },
  };
}

/** Builds the minimal payload the customer may see. */
export function displayState({ status, storeName, branchName, items = [], discount = 0, tendered = null, orderCode = null, paymentMethod = null }) {
  const lines = items.map((item) => ({
    key: String(item.variantId ?? item.sku),
    name: item.name,
    variantName: item.variantName || '',
    imageUrl: item.imageUrl || null,
    quantity: Number(item.quantity),
    unitPrice: Number(item.price ?? item.unitPrice),
    lineTotal: Number(item.price ?? item.unitPrice) * Number(item.quantity),
  }));
  const subtotal = lines.reduce((sum, line) => sum + line.lineTotal, 0);
  const safeDiscount = Math.min(Math.max(0, Number(discount) || 0), subtotal);
  const total = subtotal - safeDiscount;
  const paid = tendered === null || tendered === '' ? null : Number(tendered);
  return {
    status: status || (lines.length ? 'cart' : 'idle'),
    storeName: storeName || 'DKat',
    branchName: branchName || '',
    items: lines,
    itemCount: lines.reduce((sum, line) => sum + line.quantity, 0),
    subtotal,
    discount: safeDiscount,
    total,
    tendered: Number.isFinite(paid) ? paid : null,
    change: Number.isFinite(paid) && paid >= total ? paid - total : null,
    orderCode,
    paymentMethod,
    updatedAt: Date.now(),
  };
}
