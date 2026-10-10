const API_BASE = import.meta.env.VITE_API_URL || '/api';

export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface ApiError {
  detail: string;
  code?: string;
}

export async function apiRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: any;
    idempotencyKey?: string;
    requireAuth?: boolean;
  } = {}
): Promise<T> {
  const { method = 'GET', body, idempotencyKey, requireAuth = true } = options;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (requireAuth) {
    const token = localStorage.getItem('minipay_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errDetail = typeof data.detail === 'object' ? data.detail.detail : data.detail || 'Request failed';
    const errCode = typeof data.detail === 'object' ? data.detail.code : data.code;
    
    if (errCode === 'USER_BLOCKED' || response.status === 403 && errDetail?.toLowerCase().includes('blocked')) {
      window.dispatchEvent(new CustomEvent('minipay:user_blocked', { detail: errDetail }));
    }

    throw {
      status: response.status,
      detail: errDetail,
      code: errCode,
    };
  }

  return data as T;
}

// User & Auth APIs
export const authApi = {
  register: (email: string, password: string) =>
    apiRequest<any>('/auth/register', { method: 'POST', body: { email, password }, requireAuth: false }),
  login: (email: string, password: string) =>
    apiRequest<{ access_token: string; onboarding_step: number }>('/auth/login', {
      method: 'POST',
      body: { email, password },
      requireAuth: false,
    }),
  updateProfile: (data: { full_name: string; mobile_no: string } | string, mobile_no?: string) => {
    const body = typeof data === 'object' ? data : { full_name: data, mobile_no };
    return apiRequest<any>('/auth/profile', {
      method: 'PUT',
      body,
    });
  },
  updateAddress: (
    data: { address_line1: string; address_line2?: string; city: string; state: string; pincode: string } | string,
    address_line2?: string,
    city?: string,
    state?: string,
    pincode?: string
  ) => {
    const body =
      typeof data === 'object'
        ? data
        : { address_line1: data, address_line2, city, state, pincode };
    return apiRequest<any>('/auth/address', {
      method: 'PUT',
      body,
    });
  },
  skipBankLink: () =>
    apiRequest<any>('/auth/skip-bank-link', {
      method: 'POST',
    }),
  me: () => apiRequest<any>('/auth/me'),
};

export const walletApi = {
  getBalance: () => apiRequest<{ balance: number; currency: string }>('/wallet/balance'),
  getLedgerEntries: () => apiRequest<any[]>('/wallet/ledger-entries'),
};

export const paymentApi = {
  sendMoney: (recipient_email: string, amount: number, source: string, idempotencyKey = generateUUID()) =>
    apiRequest<any>('/payments/send', {
      method: 'POST',
      body: { recipient_email, amount, source },
      idempotencyKey,
    }),
  getTransactions: (params: { page?: number; per_page?: number; status?: string; type?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', String(params.page));
    if (params.per_page) q.set('per_page', String(params.per_page));
    if (params.status) q.set('status', params.status);
    if (params.type) q.set('type', params.type);
    return apiRequest<{ items: any[]; total: number; page: number; per_page: number }>(`/payments?${q.toString()}`);
  },
  getTransactionDetail: (id: string) => apiRequest<any>(`/payments/${id}`),
};

export const fundingApi = {
  getSources: () => apiRequest<any[]>('/funding/sources'),
  requestLink: (bank_id: string, account_no: string) =>
    apiRequest<any>('/funding/request-link', {
      method: 'POST',
      body: { bank_id, account_no },
    }),
  initiateLink: (bank_id: string) =>
    apiRequest<{ redirect_url: string; paypal_request_id: string }>('/funding/initiate-link', {
      method: 'POST',
      body: { bank_id },
    }),
  callbackLink: (bank_id: string, code: string, paypal_request_id: string) =>
    apiRequest<any>('/funding/callback', {
      method: 'POST',
      body: { bank_id, code, paypal_request_id },
    }),
  setDefault: (source_id: string) =>
    apiRequest<any>(`/funding/sources/${source_id}/default`, { method: 'PATCH' }),
  revokeSource: (source_id: string) =>
    apiRequest<any>(`/funding/sources/${source_id}`, { method: 'DELETE' }),
  addMoney: (funding_source_id: string, amount: number, idempotencyKey = generateUUID()) =>
    apiRequest<any>('/funding/add-money', {
      method: 'POST',
      body: { funding_source_id, amount },
      idempotencyKey,
    }),
  withdraw: (funding_source_id: string, amount: number, idempotencyKey = generateUUID()) =>
    apiRequest<any>('/funding/withdraw', {
      method: 'POST',
      body: { funding_source_id, amount },
      idempotencyKey,
    }),
};

// Admin APIs
export const adminApi = {
  getDashboard: () => apiRequest<any>('/admin/dashboard'),
  getUsers: (params: { search?: string; status?: string; page?: number; per_page?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.status) q.set('status', params.status);
    if (params.page) q.set('page', String(params.page));
    if (params.per_page) q.set('per_page', String(params.per_page));
    return apiRequest<{ items: any[]; total: number; page: number; per_page: number }>(`/admin/users?${q.toString()}`);
  },
  getUserDetail: (id: string) => apiRequest<any>(`/admin/users/${id}`),
  blockUser: (id: string, reason: string) =>
    apiRequest<any>(`/admin/users/${id}/block`, { method: 'POST', body: { reason } }),
  unblockUser: (id: string, reason: string) =>
    apiRequest<any>(`/admin/users/${id}/unblock`, { method: 'POST', body: { reason } }),
  unlockUser: (id: string, reason: string) =>
    apiRequest<any>(`/admin/users/${id}/unlock`, { method: 'POST', body: { reason } }),
  getTransactions: (params: { page?: number; per_page?: number; status?: string; type?: string; user_id?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', String(params.page));
    if (params.per_page) q.set('per_page', String(params.per_page));
    if (params.status) q.set('status', params.status);
    if (params.type) q.set('type', params.type);
    if (params.user_id) q.set('user_id', params.user_id);
    return apiRequest<{ items: any[]; total: number; page: number; per_page: number }>(`/admin/transactions?${q.toString()}`);
  },
  getTransactionDetail: (id: string) => apiRequest<any>(`/admin/transactions/${id}`),
  getReviewQueue: () => apiRequest<any[]>('/admin/review-queue'),
  approveTransaction: (id: string, reason: string) =>
    apiRequest<any>(`/admin/transactions/${id}/approve`, { method: 'POST', body: { reason } }),
  rejectTransaction: (id: string, reason: string) =>
    apiRequest<any>(`/admin/transactions/${id}/reject`, { method: 'POST', body: { reason } }),
  reverseTransaction: (id: string, reason: string) =>
    apiRequest<any>(`/admin/transactions/${id}/reverse`, { method: 'POST', body: { reason } }),
  getFraudConfig: () => apiRequest<any>('/admin/fraud-config'),
  updateFraudConfig: (config: any) =>
    apiRequest<any>('/admin/fraud-config', { method: 'PUT', body: config }),
  getAuditLog: (page = 1, per_page = 20) =>
    apiRequest<{ items: any[]; total: number; page: number; per_page: number }>(`/admin/audit-log?page=${page}&per_page=${per_page}`),
  getReconStatus: () => apiRequest<any>('/admin/reconciliation/status'),
  runReconciliation: () => apiRequest<any>('/admin/reconciliation/run', { method: 'POST' }),
  setBankChaos: (bank_id: string, settings: any) =>
    apiRequest<any>(`/admin/banks/${bank_id}/chaos`, { method: 'POST', body: settings }),
};

