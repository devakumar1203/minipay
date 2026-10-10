import React, { useState, useEffect, createContext, useContext } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useNavigate,
  useLocation,
  Navigate,
} from 'react-router-dom';
import {
  Wallet,
  Send,
  ArrowDownLeft,
  ArrowUpRight,
  CreditCard,
  History,
  Shield,
  Users,
  AlertTriangle,
  FileText,
  Activity,
  Settings as SettingsIcon,
  LogOut,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Lock,
  Zap,
  Building2,
  Check,
  ChevronRight,
  ChevronLeft,
  User as UserIcon,
  MapPin,
  Landmark,
  CheckCircle2,
} from 'lucide-react';
import { authApi, walletApi, paymentApi, fundingApi, adminApi } from './api/client';

// ==========================================
// AUTH CONTEXT
// ==========================================
interface UserProfile {
  id: string;
  email: string;
  role: string;
  status: string;
  onboarding_step?: number;
  full_name?: string;
  mobile_no?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  pincode?: string;
  blocked_reason?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('minipay_token'));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const u = await authApi.me();
      setUser(u);
    } catch (err: any) {
      if (err.status === 401 || err.code === 'USER_BLOCKED') {
        logout();
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, [token]);

  const login = async (newToken: string) => {
    localStorage.setItem('minipay_token', newToken);
    setToken(newToken);
    const u = await authApi.me();
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem('minipay_token');
    setToken(null);
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex items-center space-x-3 text-indigo-600 font-medium">
          <RefreshCw className="w-6 h-6 animate-spin" />
          <span>Loading MiniPay...</span>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// ==========================================
// NAVBAR & LAYOUT
// ==========================================
function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return null;

  const isAdmin = user.role === 'ADMIN';
  const isInAdmin = location.pathname.startsWith('/admin');

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2">
              <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-sm">
                P
              </div>
              <span className="font-bold text-xl text-slate-900 tracking-tight">MiniPay</span>
            </Link>

            <div className="hidden md:flex space-x-4">
              <Link
                to="/"
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  location.pathname === '/' ? 'text-indigo-600 bg-indigo-50' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/send"
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  location.pathname === '/send' ? 'text-indigo-600 bg-indigo-50' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Send Money
              </Link>
              <Link
                to="/funding"
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  location.pathname === '/funding' ? 'text-indigo-600 bg-indigo-50' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Bank Accounts
              </Link>
              <Link
                to="/transactions"
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  location.pathname === '/transactions' ? 'text-indigo-600 bg-indigo-50' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Transactions
              </Link>

              {isAdmin && (
                <Link
                  to="/admin"
                  className={`px-3 py-2 rounded-md text-sm font-medium flex items-center space-x-1.5 ${
                    isInAdmin ? 'text-amber-700 bg-amber-50 font-semibold' : 'text-amber-600 hover:text-amber-800'
                  }`}
                >
                  <Shield className="w-4 h-4" />
                  <span>Admin Panel</span>
                </Link>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-slate-900">{user.email}</div>
              <div className="text-xs text-slate-500 capitalize">{user.role.toLowerCase()}</div>
            </div>
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-md transition"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

// Blocked Account Banner
function BlockedBanner() {
  const { user } = useAuth();
  if (!user || user.status !== 'BLOCKED') return null;

  return (
    <div className="bg-red-600 text-white px-4 py-3 shadow-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="w-6 h-6 flex-shrink-0" />
          <div>
            <span className="font-bold">Account Blocked:</span> {user.blocked_reason || 'Administrative restriction.'}
            <span className="text-red-100 ml-2 text-sm">Payments, withdrawals, and incoming transfers are disabled.</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Status Badges
export function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'COMPLETED':
    case 'APPROVED':
    case 'ACTIVE':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"><CheckCircle className="w-3 h-3 mr-1" />{status}</span>;
    case 'PENDING':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"><Clock className="w-3 h-3 mr-1" />{status}</span>;
    case 'UNDER_REVIEW':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800"><AlertTriangle className="w-3 h-3 mr-1" />REVIEW</span>;
    case 'FAILED':
    case 'BLOCKED':
    case 'REVOKED':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><XCircle className="w-3 h-3 mr-1" />{status}</span>;
    case 'REVERSED':
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"><RefreshCw className="w-3 h-3 mr-1" />REVERSED</span>;
    default:
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">{status}</span>;
  }
}

// ==========================================
// PAGES: AUTH
// ==========================================
function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (user && (user.onboarding_step ?? 4) >= 4) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authApi.login(email, password);
      await login(res.access_token);
      if (res.onboarding_step && res.onboarding_step < 4) {
        navigate('/register');
      } else {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.detail || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-2xl mx-auto shadow-md mb-3">
            P
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Sign in to MiniPay</h2>
          <p className="text-sm text-slate-500 mt-1">Distributed Systems Learning Platform</p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-start space-x-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <span>Sign In</span>}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-600">
          Don't have an account?{' '}
          <Link to="/register" className="text-indigo-600 font-semibold hover:underline">
            Create account
          </Link>
        </div>

        <div className="mt-8 p-3 bg-slate-50 rounded-lg text-xs text-slate-500 border border-slate-100">
          <div className="font-semibold text-slate-700 mb-1">Demo Credentials:</div>
          <div>Admin: <code>admin@minipay.com</code> / <code>Admin123!</code></div>
        </div>
      </div>
    </div>
  );
}

function RegisterPage() {
  const { user, login, refreshUser } = useAuth();
  const navigate = useNavigate();

  // Determine initial step
  const [currentStep, setCurrentStep] = useState<number>(() => {
    if (user && user.onboarding_step) {
      return user.onboarding_step;
    }
    return 1;
  });

  useEffect(() => {
    if (user) {
      if ((user.onboarding_step ?? 4) >= 4) {
        navigate('/');
      } else if (user.onboarding_step && user.onboarding_step > currentStep) {
        setCurrentStep(user.onboarding_step);
      }
    }
  }, [user, navigate]);

  // Step 1: Credentials
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Step 2: Personal Info
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [mobileNo, setMobileNo] = useState(user?.mobile_no || '');

  // Step 3: Address Info
  const [addressLine1, setAddressLine1] = useState(user?.address_line1 || '');
  const [addressLine2, setAddressLine2] = useState(user?.address_line2 || '');
  const [city, setCity] = useState(user?.city || '');
  const [state, setState] = useState(user?.state || '');
  const [pincode, setPincode] = useState(user?.pincode || '');

  // Step 4: Bank Link
  const [selectedBank, setSelectedBank] = useState<'bank_x' | 'bank_y'>('bank_x');
  const [accountNo, setAccountNo] = useState('');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const steps = [
    { num: 1, title: 'Credentials', desc: 'Email & Password' },
    { num: 2, title: 'Profile', desc: 'Personal details' },
    { num: 3, title: 'Address', desc: 'Residential address' },
    { num: 4, title: 'Bank Link', desc: 'Connect Bank A or B' },
  ];

  // Submit Step 1
  const handleStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await authApi.register(email, password);
      const res = await authApi.login(email, password);
      await login(res.access_token);
      setCurrentStep(2);
    } catch (err: any) {
      setError(err.detail || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  // Submit Step 2
  const handleStep2 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!fullName.trim()) {
      setError('Full name is required.');
      return;
    }
    if (!/^\d{10}$/.test(mobileNo.trim())) {
      setError('Please enter a valid 10-digit mobile number.');
      return;
    }
    setLoading(true);
    try {
      await authApi.updateProfile({
        full_name: fullName.trim(),
        mobile_no: mobileNo.trim(),
      });
      await refreshUser();
      setCurrentStep(3);
    } catch (err: any) {
      setError(err.detail || 'Failed to update profile.');
    } finally {
      setLoading(false);
    }
  };

  // Submit Step 3
  const handleStep3 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!addressLine1.trim() || !city.trim() || !state.trim() || !pincode.trim()) {
      setError('Please fill in all required address fields.');
      return;
    }
    if (!/^\d{6}$/.test(pincode.trim())) {
      setError('Please enter a valid 6-digit pincode.');
      return;
    }
    setLoading(true);
    try {
      await authApi.updateAddress({
        address_line1: addressLine1.trim(),
        address_line2: addressLine2.trim() || undefined,
        city: city.trim(),
        state: state.trim(),
        pincode: pincode.trim(),
      });
      await refreshUser();
      setCurrentStep(4);
    } catch (err: any) {
      setError(err.detail || 'Failed to update address.');
    } finally {
      setLoading(false);
    }
  };

  // Submit Step 4 (Request Link)
  const handleStep4Request = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!accountNo.trim()) {
      setError('Please enter your Bank account number.');
      return;
    }
    setLoading(true);
    try {
      await fundingApi.requestLink(selectedBank, accountNo.trim());
      await refreshUser();
      navigate('/');
    } catch (err: any) {
      setError(err.detail || 'Failed to send bank link request.');
    } finally {
      setLoading(false);
    }
  };

  // Skip Step 4
  const handleStep4Skip = async () => {
    setLoading(true);
    try {
      await authApi.skipBankLink();
      await refreshUser();
      navigate('/');
    } catch (err: any) {
      setError(err.detail || 'Failed to skip bank link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-indigo-50/20 py-12 px-4 sm:px-6 lg:px-8 flex flex-col justify-center">
      <div className="max-w-xl w-full mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center text-white font-bold text-2xl mx-auto shadow-lg mb-3">
            P
          </div>
          <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Welcome to MiniPay</h2>
          <p className="text-sm text-slate-500 mt-1">Complete your onboarding journey step by step</p>
        </div>

        {/* Stepper Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sm:p-8">
          {/* Stepper Climbing Progress */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">
                Step {currentStep} of 4: {steps[currentStep - 1].title}
              </span>
              <span className="text-xs font-semibold text-slate-500">
                {Math.round((currentStep / 4) * 100)}% Complete
              </span>
            </div>
            {/* Progress line */}
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden mb-6">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${(currentStep / 4) * 100}%` }}
              />
            </div>
            {/* Steps indicator */}
            <div className="grid grid-cols-4 gap-2">
              {steps.map((s) => {
                const isCompleted = currentStep > s.num;
                const isCurrent = currentStep === s.num;
                return (
                  <div
                    key={s.num}
                    className={`flex flex-col items-center text-center p-2 rounded-lg transition ${
                      isCurrent
                        ? 'bg-indigo-50 border border-indigo-200'
                        : isCompleted
                        ? 'bg-emerald-50/50'
                        : 'opacity-50'
                    }`}
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold mb-1 ${
                        isCompleted
                          ? 'bg-emerald-600 text-white'
                          : isCurrent
                          ? 'bg-indigo-600 text-white shadow'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {isCompleted ? <Check className="w-4 h-4" /> : s.num}
                    </div>
                    <span
                      className={`text-xs font-semibold hidden sm:inline ${
                        isCurrent ? 'text-indigo-900' : isCompleted ? 'text-emerald-900' : 'text-slate-500'
                      }`}
                    >
                      {s.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-start space-x-2">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: CREDENTIALS */}
          {currentStep === 1 && (
            <form onSubmit={handleStep1} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@example.com"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Confirm Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <span>Next: Profile Info</span>
                    <ChevronRight className="w-5 h-5" />
                  </>
                )}
              </button>
              <div className="text-center pt-2 text-sm text-slate-500">
                Already have an account?{' '}
                <Link to="/login" className="text-indigo-600 font-semibold hover:underline">
                  Sign In
                </Link>
              </div>
            </form>
          )}

          {/* STEP 2: PERSONAL INFO */}
          {currentStep === 2 && (
            <form onSubmit={handleStep2} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Full Legal Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Deva Kumar"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Mobile Phone Number</label>
                <div className="relative">
                  <span className="absolute left-3.5 top-2.5 text-slate-400 font-semibold text-sm">+91</span>
                  <input
                    type="tel"
                    required
                    maxLength={10}
                    value={mobileNo}
                    onChange={(e) => setMobileNo(e.target.value.replace(/\D/g, ''))}
                    placeholder="9876543210"
                    className="w-full pl-12 pr-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1">10-digit Indian mobile number</p>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <span>Next: Address Details</span>
                    <ChevronRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* STEP 3: ADDRESS */}
          {currentStep === 3 && (
            <form onSubmit={handleStep3} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Address Line 1</label>
                <input
                  type="text"
                  required
                  value={addressLine1}
                  onChange={(e) => setAddressLine1(e.target.value)}
                  placeholder="Flat 101, Green Heights, MG Road"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Address Line 2 (Optional)</label>
                <input
                  type="text"
                  value={addressLine2}
                  onChange={(e) => setAddressLine2(e.target.value)}
                  placeholder="Near City Mall"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">City</label>
                  <input
                    type="text"
                    required
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Bengaluru"
                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">State</label>
                  <input
                    type="text"
                    required
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    placeholder="Karnataka"
                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Pincode</label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={pincode}
                  onChange={(e) => setPincode(e.target.value.replace(/\D/g, ''))}
                  placeholder="560001"
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <span>Next: Link Bank Account</span>
                    <ChevronRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* STEP 4: LINK BANK */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div className="bg-indigo-50/70 rounded-xl p-4 border border-indigo-100 text-sm text-indigo-900">
                <div className="flex items-center space-x-2 font-semibold mb-1">
                  <Landmark className="w-4 h-4 text-indigo-600" />
                  <span>Connect your Bank Account</span>
                </div>
                <p className="text-xs text-indigo-700">
                  Select your bank and enter your account number. A linking request will be sent to your bank.
                  You can immediately access your dashboard—no waiting required! You can approve the request from your bank notifications portal at any time.
                </p>
              </div>

              <form onSubmit={handleStep4Request} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Select Bank</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedBank('bank_x')}
                      className={`p-3.5 rounded-xl border flex flex-col items-center justify-center space-y-1.5 transition ${
                        selectedBank === 'bank_x'
                          ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 shadow-sm font-semibold'
                          : 'border-slate-200 hover:border-slate-300 text-slate-600'
                      }`}
                    >
                      <Building2 className="w-6 h-6 text-indigo-600" />
                      <span className="text-sm">Bank A</span>
                      <span className="text-[10px] text-slate-400">Port 3010 / 8010</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedBank('bank_y')}
                      className={`p-3.5 rounded-xl border flex flex-col items-center justify-center space-y-1.5 transition ${
                        selectedBank === 'bank_y'
                          ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 shadow-sm font-semibold'
                          : 'border-slate-200 hover:border-slate-300 text-slate-600'
                      }`}
                    >
                      <Building2 className="w-6 h-6 text-emerald-600" />
                      <span className="text-sm">Bank B</span>
                      <span className="text-[10px] text-slate-400">Port 3020 / 8020</span>
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    {selectedBank === 'bank_x' ? 'Bank A' : 'Bank B'} Account Number
                  </label>
                  <input
                    type="text"
                    required
                    value={accountNo}
                    onChange={(e) => setAccountNo(e.target.value.toUpperCase())}
                    placeholder="e.g. ACC12345678"
                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 font-mono"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Check your account number on the Bank {selectedBank === 'bank_x' ? 'A' : 'B'} web portal.
                  </p>
                </div>

                <div className="pt-2 space-y-3">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <CheckCircle2 className="w-5 h-5" />
                        <span>Send Link Request & Go to Dashboard</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={handleStep4Skip}
                    disabled={loading}
                    className="w-full py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-lg transition text-sm disabled:opacity-50"
                  >
                    Skip for now & Go to Dashboard
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==========================================
// PAGES: USER DASHBOARD
// ==========================================
function DashboardPage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState<number>(0);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [balRes, txnRes, srcRes] = await Promise.all([
        walletApi.getBalance(),
        paymentApi.getTransactions({ per_page: 5 }),
        fundingApi.getSources(),
      ]);
      setBalance(balRes.balance);
      setTransactions(txnRes.items || []);
      setSources(srcRes || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const pendingSources = sources.filter((s) => s.status === 'PENDING');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Pending Bank Linking Banner */}
      {pendingSources.length > 0 && (
        <div className="mb-6 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start space-x-3 shadow-sm">
          <Clock className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm">
            <div className="font-bold mb-1">
              Bank Account Linking Pending ({pendingSources.length} request{pendingSources.length > 1 ? 's' : ''})
            </div>
            <div>
              You requested to link{' '}
              <span className="font-semibold">
                {pendingSources
                  .map((s) => `${s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'} (${s.masked_account})`)
                  .join(', ')}
              </span>
              . MiniPay is awaiting your approval from the bank.
            </div>
            <div className="mt-2 text-xs text-amber-800 flex items-center space-x-3">
              <span>👉 Open your Bank portal:</span>
              <a
                href="http://localhost:3010/notifications"
                target="_blank"
                rel="noreferrer"
                className="underline font-bold text-indigo-700 hover:text-indigo-900"
              >
                Bank A Notifications (Port 3010)
              </a>
              <span>•</span>
              <a
                href="http://localhost:3020/notifications"
                target="_blank"
                rel="noreferrer"
                className="underline font-bold text-emerald-700 hover:text-emerald-900"
              >
                Bank B Notifications (Port 3020)
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Balance Card */}
        <div className="bg-gradient-to-br from-indigo-900 to-indigo-700 rounded-2xl p-6 text-white shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-indigo-200 text-sm font-medium mb-2">
              <span>Wallet Balance</span>
              <Wallet className="w-5 h-5" />
            </div>
            <div className="text-4xl font-extrabold tracking-tight">
              ₹{(balance / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-indigo-200 mt-1">({balance} paise)</div>
          </div>

          <div className="flex space-x-3 mt-6">
            <Link
              to="/send"
              className="flex-1 bg-white text-indigo-900 font-semibold py-2 px-3 rounded-lg text-sm text-center shadow hover:bg-indigo-50 transition"
            >
              Send
            </Link>
            <Link
              to="/funding"
              className="flex-1 bg-indigo-800 text-white font-semibold py-2 px-3 rounded-lg text-sm text-center border border-indigo-600 hover:bg-indigo-700 transition"
            >
              Add / Withdraw
            </Link>
          </div>
        </div>

        {/* Linked Banks Card */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 text-sm font-medium mb-3">
              <span>Linked Bank Accounts</span>
              <CreditCard className="w-5 h-5 text-slate-400" />
            </div>
            {sources.length === 0 ? (
              <p className="text-sm text-slate-500 py-4">No bank accounts linked yet.</p>
            ) : (
              <div className="space-y-2">
                {sources.slice(0, 2).map((s) => (
                  <div key={s.id} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                    <div>
                      <div className="text-sm font-bold text-slate-900">
                        {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'}
                      </div>
                      <div className="text-xs text-slate-500">{s.masked_account}</div>
                    </div>
                    <div>
                      {s.status === 'PENDING' ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-amber-100 text-amber-800 rounded">
                          Pending Approval
                        </span>
                      ) : s.is_default ? (
                        <span className="text-xs font-semibold px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded">Default</span>
                      ) : (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded">Active</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <Link to="/funding" className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 mt-4 block">
            Manage Banks &rarr;
          </Link>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-lg">Recent Transactions</h3>
          <Link to="/transactions" className="text-sm font-semibold text-indigo-600 hover:text-indigo-700">
            View all
          </Link>
        </div>

        {transactions.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No transactions yet.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {transactions.map((t) => (
              <div key={t.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-600">
                    {t.type === 'WITHDRAW' ? (
                      <ArrowUpRight className="w-5 h-5 text-red-600" />
                    ) : (
                      <ArrowDownLeft className="w-5 h-5 text-emerald-600" />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-slate-900">{t.type.replace('_', ' ')}</div>
                    <div className="text-xs text-slate-400">{new Date(t.created_at).toLocaleString()}</div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-sm font-bold text-slate-900">
                    ₹{(t.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="mt-0.5">
                    <StatusBadge status={t.status} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==========================================
// PAGES: SEND MONEY
// ==========================================
function SendMoneyPage() {
  const navigate = useNavigate();
  const [recipient, setRecipient] = useState('');
  const [amountInr, setAmountInr] = useState('');
  const [source, setSource] = useState('WALLET');
  const [fundingSources, setFundingSources] = useState<any[]>([]);
  const [balance, setBalance] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState<any>(null);

  useEffect(() => {
    walletApi.getBalance().then((res) => setBalance(res.balance)).catch(() => {});
    fundingApi.getSources().then((res) => setFundingSources(res)).catch(() => {});
  }, []);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(null);
    setLoading(true);

    const amountPaise = Math.round(parseFloat(amountInr) * 100);
    if (isNaN(amountPaise) || amountPaise <= 0) {
      setError('Please enter a valid amount.');
      setLoading(false);
      return;
    }

    try {
      const res = await paymentApi.sendMoney(recipient, amountPaise, source);
      setSuccess(res);
      setAmountInr('');
      setRecipient('');
    } catch (err: any) {
      setError(err.detail || 'Payment failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-10">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Send Money (P2P)</h2>
        <p className="text-sm text-slate-500 mb-6">Instant transfer to any active MiniPay user</p>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-start space-x-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">
            <div className="font-bold mb-1">Transaction {success.status}!</div>
            <div>Transaction ID: <code className="text-xs bg-white px-1 py-0.5 rounded">{success.id}</code></div>
            <div>Amount: ₹{(success.amount / 100).toFixed(2)}</div>
            <div className="mt-2">
              <StatusBadge status={success.status} />
            </div>
          </div>
        )}

        {/* Pending Bank Linking Notice */}
        {fundingSources.some((s) => s.status === 'PENDING') && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-xs flex items-start space-x-2.5">
            <Clock className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-semibold mb-0.5">Bank Account Linking Pending</div>
              <div>
                Your bank link request is awaiting approval in your Bank portal. In the meantime, you can transfer money seamlessly using your <strong>MiniPay Wallet</strong>!
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSend} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Recipient Email</label>
            <input
              type="email"
              required
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="recipient@example.com"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Amount (₹ INR)</label>
            <div className="relative">
              <span className="absolute left-3.5 top-2.5 text-slate-400 font-bold">₹</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={amountInr}
                onChange={(e) => setAmountInr(e.target.value)}
                placeholder="100.00"
                className="w-full pl-8 pr-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Payment Method</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 bg-white"
            >
              <option value="WALLET">
                MiniPay Wallet (Balance: ₹{(balance / 100).toFixed(2)})
              </option>
              {fundingSources
                .filter((s) => s.status === 'ACTIVE')
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'} ({s.masked_account}) {s.is_default ? '★ Default' : ''}
                  </option>
                ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <span>Send Payment</span>}
          </button>
        </form>
      </div>
    </div>
  );
}

// ==========================================
// PAGES: FUNDING SOURCES & BANK LINKING
// ==========================================
function FundingPage() {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [addAmount, setAddAmount] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [selectedSource, setSelectedSource] = useState('');
  const [actionMsg, setActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Manual link request state
  const [reqBank, setReqBank] = useState<'bank_x' | 'bank_y'>('bank_x');
  const [reqAccountNo, setReqAccountNo] = useState('');
  const [reqLoading, setReqLoading] = useState(false);

  const loadSources = async () => {
    try {
      const res = await fundingApi.getSources();
      setSources(res);
      const active = res.filter((s: any) => s.status === 'ACTIVE');
      if (active.length > 0 && (!selectedSource || !active.find((s: any) => s.id === selectedSource))) {
        setSelectedSource(active[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, []);

  const handleLinkBankOAuth = async (bankId: 'bank_x' | 'bank_y') => {
    try {
      const res = await fundingApi.initiateLink(bankId);
      window.location.href = res.redirect_url;
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.detail || 'Failed to initiate bank link' });
    }
  };

  const handleRequestLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionMsg(null);
    if (!reqAccountNo.trim()) {
      setActionMsg({ type: 'error', text: 'Please enter an account number.' });
      return;
    }
    setReqLoading(true);
    try {
      await fundingApi.requestLink(reqBank, reqAccountNo.trim());
      setActionMsg({
        type: 'success',
        text: `Link request sent to ${reqBank === 'bank_x' ? 'Bank A' : 'Bank B'}! Please log in to your bank account notifications to approve it.`,
      });
      setReqAccountNo('');
      await loadSources();
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.detail || 'Failed to send bank link request.' });
    } finally {
      setReqLoading(false);
    }
  };

  const handleAddMoney = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionMsg(null);
    const amountPaise = Math.round(parseFloat(addAmount) * 100);
    try {
      const res = await fundingApi.addMoney(selectedSource, amountPaise);
      if (res.status === 'FAILED') {
        setActionMsg({
          type: 'error',
          text: 'Payment failed: Insufficient bank balance.',
        });
      } else {
        setActionMsg({
          type: 'success',
          text: `Added ₹${(amountPaise / 100).toFixed(2)} to wallet! Status: ${res.status}`,
        });
        setAddAmount('');
      }
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.detail || 'Add money failed.' });
    }
  };

  const handleWithdraw = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionMsg(null);
    const amountPaise = Math.round(parseFloat(withdrawAmount) * 100);
    try {
      const res = await fundingApi.withdraw(selectedSource, amountPaise);
      if (res.status === 'FAILED') {
        setActionMsg({
          type: 'error',
          text: 'Withdrawal failed: Bank transfer failed.',
        });
      } else {
        setActionMsg({
          type: 'success',
          text: `Withdrew ₹${(amountPaise / 100).toFixed(2)} to bank! Status: ${res.status}`,
        });
        setWithdrawAmount('');
      }
    } catch (err: any) {
      setActionMsg({ type: 'error', text: err.detail || 'Withdrawal failed.' });
    }
  };

  const handleSetDefault = async (id: string) => {
    await fundingApi.setDefault(id);
    loadSources();
  };

  const handleRevoke = async (id: string) => {
    if (confirm('Revoke or cancel this bank link?')) {
      await fundingApi.revokeSource(id);
      loadSources();
    }
  };

  const activeSources = sources.filter((s) => s.status === 'ACTIVE');
  const pendingSources = sources.filter((s) => s.status === 'PENDING');

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {actionMsg && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-center justify-between shadow-sm ${
            actionMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          <span>{actionMsg.text}</span>
          <button onClick={() => setActionMsg(null)} className="font-bold text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Linked Sources List */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Linked Bank Accounts</h2>
            <p className="text-sm text-slate-500">Connect and manage Bank A & Bank B accounts</p>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={() => handleLinkBankOAuth('bank_x')}
              className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition flex items-center space-x-1"
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Link Bank A</span>
            </button>
            <button
              onClick={() => handleLinkBankOAuth('bank_y')}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-sm transition flex items-center space-x-1"
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Link Bank B</span>
            </button>
          </div>
        </div>

        {sources.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm bg-slate-50 rounded-xl border border-dashed border-slate-200">
            No bank accounts linked yet. Use the request form below or click buttons above to connect.
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map((s) => (
              <div
                key={s.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200 gap-3"
              >
                <div className="flex items-center space-x-4">
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm ${
                      s.bank_id === 'bank_x' ? 'bg-indigo-100 text-indigo-700' : 'bg-emerald-100 text-emerald-700'
                    }`}
                  >
                    {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-900">
                        {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'}
                      </span>
                      {s.status === 'PENDING' ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full flex items-center space-x-1">
                          <Clock className="w-3 h-3" />
                          <span>Pending Approval</span>
                        </span>
                      ) : s.status === 'DENIED' ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-red-100 text-red-800 rounded-full">
                          Denied
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full">
                          Active
                        </span>
                      )}
                      {s.is_default && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded-full">
                          Default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5 font-mono">{s.masked_account}</div>
                    {s.status === 'PENDING' && (
                      <div className="text-xs text-amber-700 mt-1">
                        Waiting for your approval in{' '}
                        <a
                          href={s.bank_id === 'bank_x' ? 'http://localhost:3010/notifications' : 'http://localhost:3020/notifications'}
                          target="_blank"
                          rel="noreferrer"
                          className="underline font-bold"
                        >
                          {s.bank_id === 'bank_x' ? 'Bank A Portal (Port 3010)' : 'Bank B Portal (Port 3020)'}
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end sm:self-center">
                  {s.status === 'ACTIVE' && !s.is_default && (
                    <button
                      onClick={() => handleSetDefault(s.id)}
                      className="text-xs font-medium text-indigo-600 hover:underline"
                    >
                      Make Default
                    </button>
                  )}
                  <button
                    onClick={() => handleRevoke(s.id)}
                    className="text-xs font-medium text-red-600 hover:underline"
                  >
                    {s.status === 'PENDING' ? 'Cancel Request' : 'Revoke'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Manual Request Form */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h3 className="text-lg font-bold text-slate-900 mb-1">Send Link Request by Account Number</h3>
        <p className="text-xs text-slate-500 mb-4">
          Enter your mock bank account number to notify your bank account owner for approval.
        </p>

        <form onSubmit={handleRequestLink} className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Select Bank</label>
            <select
              value={reqBank}
              onChange={(e) => setReqBank(e.target.value as 'bank_x' | 'bank_y')}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
            >
              <option value="bank_x">Bank A (Port 3010)</option>
              <option value="bank_y">Bank B (Port 3020)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Account Number</label>
            <input
              type="text"
              required
              value={reqAccountNo}
              onChange={(e) => setReqAccountNo(e.target.value.toUpperCase())}
              placeholder="e.g. ACC12345678"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono"
            />
          </div>

          <div>
            <button
              type="submit"
              disabled={reqLoading}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg text-sm shadow-sm transition flex items-center justify-center space-x-1.5 disabled:opacity-50"
            >
              {reqLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Send Link Request</span>}
            </button>
          </div>
        </form>
      </div>

      {/* Add Money & Withdraw Panels */}
      {activeSources.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Add Money */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900 mb-1">Add Money (Bank &rarr; Wallet)</h3>
            <p className="text-xs text-slate-500 mb-4">Pulls funds from linked bank account via saga</p>

            <form onSubmit={handleAddMoney} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Bank</label>
                <select
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                >
                  {activeSources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'} ({s.masked_account})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Amount (₹ INR)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={addAmount}
                  onChange={(e) => setAddAmount(e.target.value)}
                  placeholder="500.00"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <button
                type="submit"
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg text-sm shadow-sm transition"
              >
                Add to Wallet
              </button>
            </form>
          </div>

          {/* Withdraw */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-lg font-bold text-slate-900 mb-1">Withdraw (Wallet &rarr; Bank)</h3>
            <p className="text-xs text-slate-500 mb-4">Reserve-first pattern with bank credit</p>

            <form onSubmit={handleWithdraw} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Destination Bank</label>
                <select
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                >
                  {activeSources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.bank_id === 'bank_x' ? 'Bank A' : 'Bank B'} ({s.masked_account})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Amount (₹ INR)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={withdrawAmount}
                  onChange={(e) => setWithdrawAmount(e.target.value)}
                  placeholder="250.00"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>

              <button
                type="submit"
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-lg text-sm shadow-sm transition"
              >
                Withdraw to Bank
              </button>
            </form>
          </div>
        </div>
      ) : pendingSources.length > 0 ? (
        <div className="p-6 bg-amber-50 rounded-2xl border border-amber-200 text-amber-900 text-sm">
          <div className="font-bold flex items-center space-x-2 mb-1">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Bank Linking Pending Approval</span>
          </div>
          <p className="text-xs text-amber-800">
            You have bank account(s) waiting for approval in your Bank portal notifications.
            Once approved, you will be able to Add Money to your MiniPay wallet or Withdraw funds to your bank account right here!
          </p>
        </div>
      ) : null}
    </div>
  );
}

// ==========================================
// PAGES: BANK LINK CALLBACK
// ==========================================
function BankCallbackPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [statusText, setStatusText] = useState('Connecting to bank and exchanging token...');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    const bank_id = params.get('bank_id') || 'bank_x';
    const paypal_request_id = params.get('paypal_request_id') || '';

    if (!code) {
      setStatusText('Missing authorization code.');
      return;
    }

    fundingApi
      .callbackLink(bank_id, code, paypal_request_id)
      .then(() => {
        setStatusText('Bank account linked successfully! Redirecting...');
        setTimeout(() => navigate('/funding'), 1500);
      })
      .catch((err) => {
        setStatusText(`Failed to link account: ${err.detail || 'Unknown error'}`);
      });
  }, [location]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl p-8 border border-slate-200 text-center shadow-sm">
        <RefreshCw className="w-10 h-10 animate-spin text-indigo-600 mx-auto mb-4" />
        <h3 className="text-lg font-bold text-slate-900 mb-2">OAuth Bank Linking</h3>
        <p className="text-sm text-slate-600">{statusText}</p>
      </div>
    </div>
  );
}

// ==========================================
// PAGES: TRANSACTIONS LIST
// ==========================================
function TransactionsPage() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedTxn, setSelectedTxn] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  const loadTxns = async () => {
    setLoading(true);
    try {
      const res = await paymentApi.getTransactions({
        status: statusFilter || undefined,
        type: typeFilter || undefined,
        per_page: 50,
      });
      setTransactions(res.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTxns();
  }, [statusFilter, typeFilter]);

  const viewDetail = async (id: string) => {
    const detail = await paymentApi.getTransactionDetail(id);
    setSelectedTxn(detail);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Transaction History</h2>
          <p className="text-sm text-slate-500">Full ledger history and real-time status</p>
        </div>

        <div className="flex space-x-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            <option value="">All Statuses</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="PENDING">PENDING</option>
            <option value="UNDER_REVIEW">UNDER_REVIEW</option>
            <option value="FAILED">FAILED</option>
            <option value="REVERSED">REVERSED</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            <option value="">All Types</option>
            <option value="P2P_WALLET">P2P_WALLET</option>
            <option value="P2P_BANK">P2P_BANK</option>
            <option value="ADD_MONEY">ADD_MONEY</option>
            <option value="WITHDRAW">WITHDRAW</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {transactions.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-sm">No matching transactions.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <th className="px-6 py-3">Transaction ID</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Amount</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {transactions.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4 font-mono text-xs text-slate-600">{t.id}</td>
                    <td className="px-6 py-4 font-semibold text-slate-900">{t.type}</td>
                    <td className="px-6 py-4 font-bold text-slate-900">
                      ₹{(t.amount / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">{new Date(t.created_at).toLocaleString()}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => viewDetail(t.id)}
                        className="text-xs font-semibold text-indigo-600 hover:underline"
                      >
                        Inspect Saga &rarr;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transaction Detail Modal */}
      {selectedTxn && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-4 mb-4">
              <h3 className="text-lg font-bold text-slate-900">Transaction & Saga Detail</h3>
              <button onClick={() => setSelectedTxn(null)} className="text-slate-400 hover:text-slate-600 text-2xl font-bold">
                &times;
              </button>
            </div>

            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl">
                <div>
                  <span className="text-slate-500 text-xs">Transaction ID:</span>
                  <div className="font-mono text-xs font-bold">{selectedTxn.id}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Idempotency Key:</span>
                  <div className="font-mono text-xs font-bold truncate">{selectedTxn.idempotency_key}</div>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Status:</span>
                  <div><StatusBadge status={selectedTxn.status} /></div>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Amount:</span>
                  <div className="font-bold text-slate-900">₹{(selectedTxn.amount / 100).toFixed(2)}</div>
                </div>
              </div>

              {/* Double-Entry Ledger Entries */}
              <div>
                <h4 className="font-bold text-slate-900 mb-2">Double-Entry Ledger Entries (Append-Only)</h4>
                {selectedTxn.ledger_entries?.length === 0 ? (
                  <div className="text-xs text-slate-500">No ledger entries created yet (funds held or pending).</div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedTxn.ledger_entries.map((e: any) => (
                      <div key={e.id} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg text-xs">
                        <span className="font-mono text-slate-600">Account: {e.account_id}</span>
                        <span className={`font-bold px-2 py-0.5 rounded ${e.direction === 'DEBIT' ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'}`}>
                          {e.direction} ₹{(e.amount / 100).toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Saga Step History */}
              <div>
                <h4 className="font-bold text-slate-900 mb-2">Saga Orchestrator Steps</h4>
                {selectedTxn.saga_states?.length === 0 ? (
                  <div className="text-xs text-slate-500">Single-phase local transaction (no distributed saga required).</div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedTxn.saga_states.map((s: any) => (
                      <div key={s.id} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg text-xs">
                        <span className="font-semibold">{s.step}</span>
                        <div className="flex items-center space-x-2">
                          {s.error_detail && <span className="text-red-500 truncate max-w-xs">{s.error_detail}</span>}
                          <StatusBadge status={s.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// ADMIN PANEL
// ==========================================
function AdminLayout() {
  const { user } = useAuth();
  if (!user || user.role !== 'ADMIN') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center space-x-3 mb-6 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
          <Shield className="w-6 h-6 text-amber-600" />
          <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">MiniPay Administrator Control Panel</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Admin Sidebar Navigation */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-1 h-fit">
            <Link to="/admin" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <Activity className="w-4 h-4 text-indigo-600" />
              <span>Dashboard</span>
            </Link>
            <Link to="/admin/users" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <Users className="w-4 h-4 text-indigo-600" />
              <span>Users & Blocking</span>
            </Link>
            <Link to="/admin/review" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <AlertTriangle className="w-4 h-4 text-orange-600" />
              <span>Fraud Review Queue</span>
            </Link>
            <Link to="/admin/transactions" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <History className="w-4 h-4 text-indigo-600" />
              <span>Transactions & Reversals</span>
            </Link>
            <Link to="/admin/reconciliation" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <RefreshCw className="w-4 h-4 text-indigo-600" />
              <span>Reconciliation</span>
            </Link>
            <Link to="/admin/fraud-config" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <SettingsIcon className="w-4 h-4 text-indigo-600" />
              <span>Fraud Thresholds</span>
            </Link>
            <Link to="/admin/chaos" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <Zap className="w-4 h-4 text-amber-600" />
              <span>Bank Chaos Controls</span>
            </Link>
            <Link to="/admin/audit" className="flex items-center space-x-2.5 px-3 py-2 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50">
              <FileText className="w-4 h-4 text-slate-500" />
              <span>Audit Log</span>
            </Link>
          </div>

          {/* Admin Content Area */}
          <div className="md:col-span-3">
            <Routes>
              <Route path="/" element={<AdminDashboardPage />} />
              <Route path="/users" element={<AdminUsersPage />} />
              <Route path="/review" element={<AdminReviewQueuePage />} />
              <Route path="/transactions" element={<AdminTransactionsPage />} />
              <Route path="/reconciliation" element={<AdminReconciliationPage />} />
              <Route path="/fraud-config" element={<AdminFraudConfigPage />} />
              <Route path="/chaos" element={<AdminChaosPage />} />
              <Route path="/audit" element={<AdminAuditLogPage />} />
            </Routes>
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminDashboardPage() {
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    adminApi.getDashboard().then(setMetrics);
  }, []);

  if (!metrics) return <div>Loading dashboard metrics...</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase">Total Users</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{metrics.total_users}</div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase">Blocked Users</div>
          <div className="text-2xl font-bold text-red-600 mt-1">{metrics.blocked_users}</div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase">Total Volume</div>
          <div className="text-2xl font-bold text-indigo-600 mt-1">₹{(metrics.total_volume / 100).toFixed(2)}</div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase">Failure Rate</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{metrics.failure_rate}%</div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 mb-4">Transaction Counts by Status</h3>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {Object.entries(metrics.txn_counts_by_status || {}).map(([st, count]) => (
            <div key={st} className="p-3 bg-slate-50 rounded-lg text-center">
              <div className="text-xs text-slate-500 font-semibold">{st}</div>
              <div className="text-lg font-bold text-slate-900 mt-0.5">{String(count)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [reason, setReason] = useState('');
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const [actionType, setActionType] = useState<'block' | 'unblock' | 'unlock' | null>(null);

  const loadUsers = async () => {
    const res = await adminApi.getUsers({ search });
    setUsers(res.items || []);
  };

  useEffect(() => {
    loadUsers();
  }, [search]);

  const handleAction = async () => {
    if (!selectedUser || !reason) return;
    try {
      if (actionType === 'block') {
        await adminApi.blockUser(selectedUser.id, reason);
      } else if (actionType === 'unblock') {
        await adminApi.unblockUser(selectedUser.id, reason);
      } else if (actionType === 'unlock') {
        await adminApi.unlockUser(selectedUser.id, reason);
      }
      setSelectedUser(null);
      setActionType(null);
      setReason('');
      loadUsers();
    } catch (err: any) {
      alert(err.detail || 'Action failed');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-900">User Management & Propagation</h3>
        <input
          type="text"
          placeholder="Search by email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3 font-medium">{u.email}</td>
                <td className="px-4 py-3 capitalize">{u.role}</td>
                <td className="px-4 py-3"><StatusBadge status={u.status} /></td>
                <td className="px-4 py-3 space-x-2">
                  {u.status === 'ACTIVE' ? (
                    <button
                      onClick={() => { setSelectedUser(u); setActionType('block'); }}
                      className="text-xs font-semibold text-red-600 hover:underline"
                    >
                      Block
                    </button>
                  ) : (
                    <button
                      onClick={() => { setSelectedUser(u); setActionType('unblock'); }}
                      className="text-xs font-semibold text-emerald-600 hover:underline"
                    >
                      Unblock
                    </button>
                  )}
                  <button
                    onClick={() => { setSelectedUser(u); setActionType('unlock'); }}
                    className="text-xs font-semibold text-slate-600 hover:underline"
                  >
                    Unlock Lockout
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {actionType && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4">
            <h4 className="font-bold text-slate-900 capitalize">{actionType} User: {selectedUser.email}</h4>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reason (Mandatory Audit Log)</label>
              <textarea
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for this administrative action..."
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button onClick={() => { setSelectedUser(null); setActionType(null); }} className="px-3 py-1.5 text-sm text-slate-600">
                Cancel
              </button>
              <button onClick={handleAction} className="px-4 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg">
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminReviewQueuePage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [selectedTxn, setSelectedTxn] = useState<any | null>(null);
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);
  const [reason, setReason] = useState('');

  const loadQueue = async () => {
    const res = await adminApi.getReviewQueue();
    setQueue(res || []);
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleDecision = async () => {
    if (!selectedTxn || !reason) return;
    try {
      if (action === 'approve') {
        await adminApi.approveTransaction(selectedTxn.id, reason);
      } else {
        await adminApi.rejectTransaction(selectedTxn.id, reason);
      }
      setSelectedTxn(null);
      setAction(null);
      setReason('');
      loadQueue();
    } catch (err: any) {
      alert(err.detail || 'Decision failed');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <h3 className="text-lg font-bold text-slate-900">Fraud Review Queue</h3>

      {queue.length === 0 ? (
        <div className="p-8 text-center text-slate-500 text-sm">No transactions currently under review.</div>
      ) : (
        <div className="space-y-3">
          {queue.map((t) => (
            <div key={t.id} className="p-4 bg-orange-50 border border-orange-200 rounded-xl flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">{t.type} — ₹{(t.amount / 100).toFixed(2)}</div>
                <div className="text-xs text-slate-600 font-mono">Txn: {t.id}</div>
                <div className="text-xs text-slate-400">{new Date(t.created_at).toLocaleString()}</div>
              </div>

              <div className="flex space-x-2">
                <button
                  onClick={() => { setSelectedTxn(t); setAction('approve'); }}
                  className="px-3 py-1.5 bg-emerald-600 text-white font-semibold text-xs rounded-lg shadow-sm"
                >
                  Approve
                </button>
                <button
                  onClick={() => { setSelectedTxn(t); setAction('reject'); }}
                  className="px-3 py-1.5 bg-red-600 text-white font-semibold text-xs rounded-lg shadow-sm"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {action && selectedTxn && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4">
            <h4 className="font-bold text-slate-900 capitalize">{action} Transaction</h4>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reason</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for decision..."
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button onClick={() => { setSelectedTxn(null); setAction(null); }} className="px-3 py-1.5 text-sm text-slate-600">
                Cancel
              </button>
              <button onClick={handleDecision} className="px-4 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg">
                Submit Decision
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminTransactionsPage() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [selectedTxn, setSelectedTxn] = useState<any | null>(null);
  const [reversalReason, setReversalReason] = useState('');

  const loadTxns = async () => {
    const res = await adminApi.getTransactions({ per_page: 50 });
    setTransactions(res.items || []);
  };

  useEffect(() => {
    loadTxns();
  }, []);

  const handleReverse = async () => {
    if (!selectedTxn || !reversalReason) return;
    try {
      await adminApi.reverseTransaction(selectedTxn.id, reversalReason);
      alert('Transaction reversed with compensating ledger entries!');
      setSelectedTxn(null);
      setReversalReason('');
      loadTxns();
    } catch (err: any) {
      alert(err.detail || 'Reversal failed');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <h3 className="text-lg font-bold text-slate-900">System Transactions & Reversals</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
              <th className="px-4 py-3">Txn ID</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transactions.map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-3 font-mono text-xs">{t.id}</td>
                <td className="px-4 py-3 font-semibold">{t.type}</td>
                <td className="px-4 py-3 font-bold">₹{(t.amount / 100).toFixed(2)}</td>
                <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
                <td className="px-4 py-3 space-x-2">
                  {t.status === 'COMPLETED' && t.type.startsWith('P2P') && (
                    <button
                      onClick={() => setSelectedTxn(t)}
                      className="text-xs font-semibold text-purple-600 hover:underline"
                    >
                      Reverse P2P
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedTxn && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4">
            <h4 className="font-bold text-slate-900">Reverse P2P Transaction: ₹{(selectedTxn.amount / 100).toFixed(2)}</h4>
            <p className="text-xs text-slate-500">
              Creates new compensating ledger entries moving funds back from recipient to sender.
            </p>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reversal Reason</label>
              <textarea
                value={reversalReason}
                onChange={(e) => setReversalReason(e.target.value)}
                placeholder="Audit log reason..."
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button onClick={() => setSelectedTxn(null)} className="px-3 py-1.5 text-sm text-slate-600">
                Cancel
              </button>
              <button onClick={handleReverse} className="px-4 py-1.5 bg-purple-600 text-white text-sm font-semibold rounded-lg">
                Execute Reversal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminReconciliationPage() {
  const [reconData, setReconData] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const loadStatus = async () => {
    const res = await adminApi.getReconStatus();
    setReconData(res);
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const triggerRun = async () => {
    setRunning(true);
    try {
      const res = await adminApi.runReconciliation();
      setReconData(res);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900">Automated Ledger Reconciliation</h3>
          <p className="text-sm text-slate-500">
            Last run: {reconData?.last_run ? new Date(reconData.last_run).toLocaleString() : 'Never'}
          </p>
        </div>

        <button
          onClick={triggerRun}
          disabled={running}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-lg shadow-sm flex items-center space-x-2 disabled:opacity-50"
        >
          {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Run Reconciliation Now</span>}
        </button>
      </div>

      <div>
        <h4 className="font-bold text-slate-900 mb-2">Discrepancy Report</h4>
        {!reconData?.discrepancies || reconData.discrepancies.length === 0 ? (
          <div className="p-6 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>All accounts and ledger entries perfectly balanced. Zero discrepancies detected.</span>
          </div>
        ) : (
          <div className="space-y-2">
            {reconData.discrepancies.map((d: any, idx: number) => (
              <div key={idx} className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs">
                {JSON.stringify(d)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AdminFraudConfigPage() {
  const [config, setConfig] = useState<any>(null);
  const [savedMsg, setSavedMsg] = useState('');

  useEffect(() => {
    adminApi.getFraudConfig().then(setConfig);
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg('');
    await adminApi.updateFraudConfig(config);
    setSavedMsg('Fraud configuration updated successfully!');
  };

  if (!config) return <div>Loading config...</div>;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <h3 className="text-lg font-bold text-slate-900">Configurable Fraud Rule Engine</h3>

      {savedMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm">
          {savedMsg}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-4 max-w-lg text-sm">
        <div>
          <label className="block font-semibold text-slate-700 mb-1">Max Transaction Amount (Paise)</label>
          <input
            type="number"
            value={config.max_txn_amount}
            onChange={(e) => setConfig({ ...config, max_txn_amount: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg"
          />
          <span className="text-xs text-slate-400">₹{(config.max_txn_amount / 100).toFixed(2)}</span>
        </div>

        <div>
          <label className="block font-semibold text-slate-700 mb-1">Daily Max Volume per User (Paise)</label>
          <input
            type="number"
            value={config.daily_max_amount}
            onChange={(e) => setConfig({ ...config, daily_max_amount: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg"
          />
          <span className="text-xs text-slate-400">₹{(config.daily_max_amount / 100).toFixed(2)}</span>
        </div>

        <div>
          <label className="block font-semibold text-slate-700 mb-1">Velocity Limit (Payments per Minute)</label>
          <input
            type="number"
            value={config.max_txn_per_minute}
            onChange={(e) => setConfig({ ...config, max_txn_per_minute: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border rounded-lg"
          />
        </div>

        <button type="submit" className="py-2.5 px-5 bg-indigo-600 text-white font-semibold rounded-lg text-sm shadow-sm">
          Save Configuration
        </button>
      </form>
    </div>
  );
}

function AdminChaosPage() {
  const [bankXChaos, setBankXChaos] = useState({ latency_ms: 0, error_probability: 0.0, drop_response: false, down: false });
  const [bankYChaos, setBankYChaos] = useState({ latency_ms: 0, error_probability: 0.0, drop_response: false, down: false });
  const [msg, setMsg] = useState('');

  const updateBank = async (bankId: 'bank_x' | 'bank_y', cfg: any) => {
    setMsg('');
    await adminApi.setBankChaos(bankId, cfg);
    setMsg(`Updated chaos controls for ${bankId.toUpperCase()}`);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <div>
        <h3 className="text-lg font-bold text-slate-900">Distributed Systems Chaos Simulation</h3>
        <p className="text-sm text-slate-500">Inject latency, timeouts, response drops, or outages into mock banks</p>
      </div>

      {msg && <div className="p-3 bg-indigo-50 text-indigo-700 rounded-lg text-sm">{msg}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Bank A */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <h4 className="font-bold text-slate-900">Bank A Chaos Controls</h4>
          <div>
            <label className="block text-xs font-semibold text-slate-700">Added Latency (ms)</label>
            <input
              type="number"
              value={bankXChaos.latency_ms}
              onChange={(e) => setBankXChaos({ ...bankXChaos, latency_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-2.5 py-1.5 border rounded text-sm bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700">Error Probability (0.0 - 1.0)</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={bankXChaos.error_probability}
              onChange={(e) => setBankXChaos({ ...bankXChaos, error_probability: parseFloat(e.target.value) || 0 })}
              className="w-full px-2.5 py-1.5 border rounded text-sm bg-white"
            />
          </div>
          <div className="flex items-center space-x-4 pt-2">
            <label className="flex items-center space-x-2 text-xs font-semibold">
              <input
                type="checkbox"
                checked={bankXChaos.drop_response}
                onChange={(e) => setBankXChaos({ ...bankXChaos, drop_response: e.target.checked })}
              />
              <span>Drop Response</span>
            </label>
            <label className="flex items-center space-x-2 text-xs font-semibold text-red-600">
              <input
                type="checkbox"
                checked={bankXChaos.down}
                onChange={(e) => setBankXChaos({ ...bankXChaos, down: e.target.checked })}
              />
              <span>Bank Down (503)</span>
            </label>
          </div>
          <button
            onClick={() => updateBank('bank_x', bankXChaos)}
            className="w-full py-2 bg-indigo-600 text-white font-semibold rounded text-xs shadow-sm mt-3"
          >
            Apply Bank A Chaos
          </button>
        </div>

        {/* Bank B */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <h4 className="font-bold text-slate-900">Bank B Chaos Controls</h4>
          <div>
            <label className="block text-xs font-semibold text-slate-700">Added Latency (ms)</label>
            <input
              type="number"
              value={bankYChaos.latency_ms}
              onChange={(e) => setBankYChaos({ ...bankYChaos, latency_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-2.5 py-1.5 border rounded text-sm bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700">Error Probability (0.0 - 1.0)</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={bankYChaos.error_probability}
              onChange={(e) => setBankYChaos({ ...bankYChaos, error_probability: parseFloat(e.target.value) || 0 })}
              className="w-full px-2.5 py-1.5 border rounded text-sm bg-white"
            />
          </div>
          <div className="flex items-center space-x-4 pt-2">
            <label className="flex items-center space-x-2 text-xs font-semibold">
              <input
                type="checkbox"
                checked={bankYChaos.drop_response}
                onChange={(e) => setBankYChaos({ ...bankYChaos, drop_response: e.target.checked })}
              />
              <span>Drop Response</span>
            </label>
            <label className="flex items-center space-x-2 text-xs font-semibold text-red-600">
              <input
                type="checkbox"
                checked={bankYChaos.down}
                onChange={(e) => setBankYChaos({ ...bankYChaos, down: e.target.checked })}
              />
              <span>Bank Down (503)</span>
            </label>
          </div>
          <button
            onClick={() => updateBank('bank_y', bankYChaos)}
            className="w-full py-2 bg-slate-800 text-white font-semibold rounded text-xs shadow-sm mt-3"
          >
            Apply Bank B Chaos
          </button>
        </div>
      </div>
    </div>
  );
}

function AdminAuditLogPage() {
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    adminApi.getAuditLog().then((res) => setLogs(res.items || []));
  }, []);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      <h3 className="text-lg font-bold text-slate-900">Immutable Administrative Audit Trail</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Target</th>
              <th className="px-4 py-3">Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-3 text-xs text-slate-500">{new Date(l.created_at).toLocaleString()}</td>
                <td className="px-4 py-3 font-bold text-slate-900">{l.action}</td>
                <td className="px-4 py-3 text-xs font-mono">{l.target_type}: {l.target_id}</td>
                <td className="px-4 py-3 text-slate-700">{l.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ==========================================
// ROOT APP
// ==========================================
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
          <BlockedBanner />
          <Navbar />
          <main className="flex-1">
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
              <Route path="/send" element={<ProtectedRoute><SendMoneyPage /></ProtectedRoute>} />
              <Route path="/funding" element={<ProtectedRoute><FundingPage /></ProtectedRoute>} />
              <Route path="/funding/callback" element={<ProtectedRoute><BankCallbackPage /></ProtectedRoute>} />
              <Route path="/transactions" element={<ProtectedRoute><TransactionsPage /></ProtectedRoute>} />
              <Route path="/admin/*" element={<ProtectedRoute><AdminLayout /></ProtectedRoute>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </Router>
    </AuthProvider>
  );
}

