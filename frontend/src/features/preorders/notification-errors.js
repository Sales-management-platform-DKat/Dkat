// Provider error codes (backend core/sms.py, core/mailer.py) -> a reason staff can act on.
// The raw text stays in the cell's tooltip for whoever configures the provider.
const DELIVERY_ERRORS = [
  [/^NOT_CONFIGURED/, 'preorder.notification.error.notConfigured'],
  [/^(AUTH_FAILED|SMTP_AUTH_FAILED|ACCOUNT_ERROR|IP_NOT_WHITELISTED|BRANDNAME_INVALID|TEMPLATE_MISMATCH)/, 'preorder.notification.error.account'],
  [/^(QUOTA_EXCEEDED|LIMIT_REACHED)/, 'preorder.notification.error.quota'],
  [/^(INVALID_PHONE|PHONE_BLOCKED|CARRIER_REJECTED|CARRIER_NOT_REGISTERED|BLOCKED_KEYWORD)/, 'preorder.notification.error.phone'],
  [/^(RECIPIENT_REFUSED|SENDER_REFUSED)/, 'preorder.notification.error.email'],
  [/^NO_CONTACT/, 'preorder.notification.error.noContact'],
  [/^RETRY_EXHAUSTED/, 'preorder.notification.error.exhausted'],
  [/^DEMO_PROVIDER_OFFLINE/, 'preorder.notification.error.demo'],
  [/^(CONNECTION_FAILED|TIMEOUT|HTTP_ERROR|INVALID_RESPONSE|PROVIDER_ERROR|SMTP_ERROR|TLS_ERROR)/, 'preorder.notification.error.connection'],
];
export function deliveryErrorKey(errorMessage) {
  if (!errorMessage) return '';
  return DELIVERY_ERRORS.find(([pattern]) => pattern.test(errorMessage))?.[1] || 'preorder.notification.error.unknown';
}
