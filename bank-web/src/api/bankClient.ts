const BANK_API_BASE = import.meta.env.VITE_BANK_API_URL || '';

export async function bankApiRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: any;
    requireAuth?: boolean;
  } = {}
): Promise<T> {
  const { method = 'GET', body, requireAuth = true } = options;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (requireAuth) {
    const token = localStorage.getItem('bank_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${BANK_API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errDetail = typeof data.detail === 'object' ? data.detail.detail : data.detail || 'Request failed';
    throw {
      status: response.status,
      detail: errDetail,
      code: data.code,
    };
  }

  return data as T;
}

export const bankAuthApi = {
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    gender: string;
    date_of_birth: string;
    aadhaar_no: string;
    pan_no: string;
  }) =>
    bankApiRequest<any>('/auth/register', {
      method: 'POST',
      body: data,
      requireAuth: false,
    }),
  login: (email: string, password: string) =>
    bankApiRequest<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: { email, password },
      requireAuth: false,
    }),
  me: () => bankApiRequest<any>('/auth/me'),
};

export const bankAccountsApi = {
  getAccounts: () => bankApiRequest<any[]>('/accounts'),
  getTransactions: (account_no: string) => bankApiRequest<any[]>(`/accounts/${account_no}/transactions`),
};

export const bankLinkingApi = {
  getConsents: () => bankApiRequest<any[]>('/linking/consents'),
  approveConsent: (account_no: string, paypal_request_id: string, per_txn_limit = 5000000) =>
    bankApiRequest<{ authorization_code: string; consent_id: string; paypal_request_id: string }>('/linking/consent', {
      method: 'POST',
      body: { account_no, paypal_request_id, per_txn_limit },
    }),
  approveRequest: (requestId: string) =>
    bankApiRequest<{ status: string; consent_id: string; token: string; masked_account: string }>(
      `/linking/approve-request/${requestId}`,
      { method: 'POST' }
    ),
  denyRequest: (requestId: string) =>
    bankApiRequest<{ status: string; request_id: string }>(`/linking/deny-request/${requestId}`, {
      method: 'POST',
    }),
  revokeConsent: (consent_id: string) =>
    bankApiRequest<any>(`/linking/revoke/${consent_id}`, { method: 'POST' }),
};

export const bankNotificationsApi = {
  getNotifications: () => bankApiRequest<any[]>('/notifications'),
  getUnreadCount: () => bankApiRequest<{ unread_count: number }>('/notifications/unread-count'),
  markAsRead: (id: string) => bankApiRequest<any>(`/notifications/${id}/read`, { method: 'PATCH' }),
};
