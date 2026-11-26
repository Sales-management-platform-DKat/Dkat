import { useEffect, useRef, useState } from 'react';
import { createDisplayPublisher } from './channel.js';

/**
 * POS hook: keeps the Customer Display in sync with `state` (see displayState)
 * and exposes open()/connected for the "Màn hình khách hàng" button.
 */
export function useCustomerDisplay(state) {
  const publisher = useRef(null);
  const latest = useRef(state);
  const [connected, setConnected] = useState(false);
  const [blockedUrl, setBlockedUrl] = useState('');

  useEffect(() => {
    publisher.current = createDisplayPublisher({ onConnectionChange: setConnected });
    if (latest.current) publisher.current.publish(latest.current);
    return () => { publisher.current?.destroy(); publisher.current = null; };
  }, []);

  useEffect(() => {
    latest.current = state;
    if (state) publisher.current?.publish(state);
  }, [state]);

  function open() {
    const result = publisher.current?.open() || { ok: false };
    setBlockedUrl(result.blocked ? result.url : '');
    if (result.ok && latest.current) setTimeout(() => publisher.current?.publish(latest.current), 400);
    return result;
  }

  return { open, connected, blockedUrl, dismissBlocked: () => setBlockedUrl('') };
}
