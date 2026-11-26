import { apiRequest } from '../../auth-client.js';

const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const getMyStore = () => apiRequest('/stores/me');
export const updateMyStore = (name) => apiRequest('/stores/me', json('PUT', { name }));
export const updateProfile = (profile) => apiRequest('/auth/me', json('PUT', profile));
export const changePassword = (currentPassword, newPassword) =>
  apiRequest('/auth/change-password', json('POST', { current_password: currentPassword, new_password: newPassword }));
export const getSessionSummary = () => apiRequest('/auth/sessions');
export const revokeOtherSessions = () => apiRequest('/auth/sessions/revoke-others', { method: 'POST' });
