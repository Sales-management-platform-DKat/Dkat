// Kept for old imports only. There must be a single confirmation host: an
// earlier dialog here listened to the same 'dkat-confirm' event as the overlay
// ConfirmHost, so every confirmation opened two stacked dialogs.
export { confirmAction, ConfirmHost } from './overlay/index.js';
