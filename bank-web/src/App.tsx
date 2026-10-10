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
  Building2,
  Wallet,
  ArrowDownLeft,
  ArrowUpRight,
  ShieldCheck,
  LogOut,
  RefreshCw,
  AlertCircle,
  Key,
  Bell,
  Check,
  ChevronRight,
  ChevronLeft,
  User,
  FileText,
  CheckCircle2,
} from 'lucide-react';
import {
  bankAuthApi,
  bankAccountsApi,
  bankLinkingApi,
  bankNotificationsApi,
} from './api/bankClient';

const BANK_NAME = import.meta.env.VITE_BANK_NAME || 'Bank';
const PAYPAL_URL = import.meta.env.VITE_PAYPAL_URL || 'http://localhost:3000';

// Auth Context
interface BankAuthContextType {
  user: any | null;
  token: string | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const BankAuthContext = createContext<BankAuthContextType>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
});

const useBankAuth = () => useContext(BankAuthContext);

function BankAuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('bank_token'));
  const [user, setUser] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const u = await bankAuthApi.me();
      setUser(u);
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [token]);

  const login = async (newToken: string) => {
    localStorage.setItem('bank_token', newToken);
    setToken(newToken);
    const u = await bankAuthApi.me();
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem('bank_token');
    setToken(null);
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <RefreshCw className="w-6 h-6 animate-spin text-slate-600" />
      </div>
    );
  }

  return (
    <BankAuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </BankAuthContext.Provider>
  );
}

// Navbar with Notification Bell
function BankNavbar() {
  const { user, logout } = useBankAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  const fetchUnread = () => {
    if (user) {
      bankNotificationsApi
        .getUnreadCount()
        .then((res) => setUnreadCount(res.unread_count))
        .catch(() => {});
    }
  };

  useEffect(() => {
    fetchUnread();
    const interval = setInterval(fetchUnread, 6000);
    return () => clearInterval(interval);
  }, [user]);

  if (!user) {
    return (
      <nav className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link to="/login" className="flex items-center space-x-3">
              <Building2 className="w-6 h-6 text-emerald-400" />
              <span className="font-bold text-lg tracking-tight">{BANK_NAME} Online Banking</span>
            </Link>
            <div className="flex items-center space-x-3">
              <Link
                to="/login"
                className="text-sm px-3.5 py-1.5 text-slate-300 hover:text-white rounded-lg transition"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="text-sm px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition shadow-sm"
              >
                Open Account
              </Link>
            </div>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Link to="/" className="flex items-center space-x-3">
            <Building2 className="w-6 h-6 text-emerald-400" />
            <span className="font-bold text-lg tracking-tight">{BANK_NAME} Online Banking</span>
          </Link>

          <div className="flex items-center space-x-6">
            <Link
              to="/"
              className={`text-sm ${
                location.pathname === '/' ? 'text-white font-semibold' : 'text-slate-300 hover:text-white'
              }`}
            >
              Accounts
            </Link>
            <Link
              to="/consents"
              className={`text-sm ${
                location.pathname === '/consents'
                  ? 'text-white font-semibold'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              Linked Apps
            </Link>

            <Link
              to="/notifications"
              className="relative p-1.5 text-slate-300 hover:text-white transition"
              title="Notifications"
            >
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full h-4.5 min-w-4.5 px-1 flex items-center justify-center animate-pulse">
                  {unreadCount}
                </span>
              )}
            </Link>

            <div className="text-xs text-slate-400 border-l border-slate-700 pl-4">{user.email}</div>
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="text-slate-400 hover:text-white"
              title="Sign Out"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

// Login
function BankLoginPage() {
  const { login, user } = useBankAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  if (user) {
    const returnUrl = new URLSearchParams(location.search).get('returnUrl') || '/';
    return <Navigate to={returnUrl} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await bankAuthApi.login(email, password);
      await login(res.access_token);
      const returnUrl = new URLSearchParams(location.search).get('returnUrl') || '/';
      navigate(returnUrl);
    } catch (err: any) {
      setError(err.detail || 'Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="max-w-md w-full bg-slate-800 rounded-2xl p-8 border border-slate-700 text-white">
        <div className="text-center mb-6">
          <Building2 className="w-12 h-12 text-emerald-400 mx-auto mb-2" />
          <h2 className="text-2xl font-bold">{BANK_NAME} Sign In</h2>
          <p className="text-xs text-slate-400 mt-1">Core Banking Portal</p>
        </div>

        {error && <div className="p-3 bg-red-900/50 text-red-200 rounded-lg text-sm mb-4">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <button
            type="submit"
            className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 font-semibold rounded-lg text-sm transition"
          >
            Sign In
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-400">
          Need an account?{' '}
          <Link to="/register" className="text-emerald-400 hover:underline">
            Open account with ₹10,000 seed
          </Link>
        </div>
      </div>
    </div>
  );
}

// 3-Step Guided Bank Registration Wizard
function BankRegisterPage() {
  const { login, user } = useBankAuth();
  const navigate = useNavigate();

  // Wizard Step (1, 2, 3)
  const [step, setStep] = useState<number>(1);

  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [fullName, setFullName] = useState('');
  const [gender, setGender] = useState<'MALE' | 'FEMALE' | 'OTHER'>('MALE');
  const [dob, setDob] = useState('');

  const [aadhaarNo, setAadhaarNo] = useState('');
  const [panNo, setPanNo] = useState('');
  const [agreedTerms, setAgreedTerms] = useState(false);

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const validateStep1 = () => {
    if (!email || !password) {
      setError('Please fill all required fields');
      return false;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return false;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    setError('');
    return true;
  };

  const validateStep2 = () => {
    if (!fullName.trim() || fullName.trim().length < 2) {
      setError('Please enter your full legal name');
      return false;
    }
    if (!dob) {
      setError('Please select your date of birth');
      return false;
    }
    setError('');
    return true;
  };

  const validateStep3 = () => {
    const cleanAadhaar = aadhaarNo.replace(/\s+/g, '');
    if (!/^\d{12}$/.test(cleanAadhaar)) {
      setError('Aadhaar number must be exactly 12 digits');
      return false;
    }
    const cleanPan = panNo.trim().toUpperCase();
    if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(cleanPan)) {
      setError('PAN number format must be 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)');
      return false;
    }
    if (!agreedTerms) {
      setError('Please accept the KYC declaration terms');
      return false;
    }
    setError('');
    return true;
  };

  const handleNext = () => {
    if (step === 1 && validateStep1()) setStep(2);
    else if (step === 2 && validateStep2()) setStep(3);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep3()) return;

    setLoading(true);
    setError('');
    try {
      const cleanAadhaar = aadhaarNo.replace(/\s+/g, '');
      const cleanPan = panNo.trim().toUpperCase();

      await bankAuthApi.register({
        email,
        password,
        full_name: fullName.trim(),
        gender,
        date_of_birth: dob,
        aadhaar_no: cleanAadhaar,
        pan_no: cleanPan,
      });

      const res = await bankAuthApi.login(email, password);
      await login(res.access_token);
      navigate('/');
    } catch (err: any) {
      setError(err.detail || 'Registration failed');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4 py-12">
      <div className="max-w-lg w-full bg-slate-800 rounded-3xl p-8 border border-slate-700 text-white shadow-2xl">
        <div className="text-center mb-6">
          <Building2 className="w-12 h-12 text-emerald-400 mx-auto mb-2" />
          <h2 className="text-2xl font-bold">Open {BANK_NAME} Account</h2>
          <p className="text-xs text-slate-400 mt-1">
            Complete onboarding to receive an instant ₹10,000 (10,00,000 paise) Seed Balance
          </p>
        </div>

        {/* Stepper Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between relative">
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-slate-700 z-0">
              <div
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: step === 1 ? '0%' : step === 2 ? '50%' : '100%' }}
              />
            </div>

            {/* Step 1 Circle */}
            <div className="relative z-10 flex flex-col items-center">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs transition ${
                  step > 1
                    ? 'bg-emerald-500 text-slate-950'
                    : step === 1
                    ? 'bg-emerald-500 text-slate-950 ring-4 ring-emerald-500/20'
                    : 'bg-slate-700 text-slate-400'
                }`}
              >
                {step > 1 ? <Check className="w-5 h-5 stroke-[3]" /> : '1'}
              </div>
              <span className="text-[11px] font-medium mt-1.5 text-slate-300">Login</span>
            </div>

            {/* Step 2 Circle */}
            <div className="relative z-10 flex flex-col items-center">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs transition ${
                  step > 2
                    ? 'bg-emerald-500 text-slate-950'
                    : step === 2
                    ? 'bg-emerald-500 text-slate-950 ring-4 ring-emerald-500/20'
                    : 'bg-slate-700 text-slate-400'
                }`}
              >
                {step > 2 ? <Check className="w-5 h-5 stroke-[3]" /> : '2'}
              </div>
              <span className="text-[11px] font-medium mt-1.5 text-slate-300">Profile</span>
            </div>

            {/* Step 3 Circle */}
            <div className="relative z-10 flex flex-col items-center">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs transition ${
                  step === 3
                    ? 'bg-emerald-500 text-slate-950 ring-4 ring-emerald-500/20'
                    : 'bg-slate-700 text-slate-400'
                }`}
              >
                3
              </div>
              <span className="text-[11px] font-medium mt-1.5 text-slate-300">KYC</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-900/60 border border-red-700/60 text-red-200 rounded-xl text-xs mb-6 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* STEP 1: LOGIN CREDENTIALS */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="border-b border-slate-700/60 pb-3 mb-4">
              <h3 className="font-semibold text-slate-200 text-sm flex items-center space-x-2">
                <Key className="w-4 h-4 text-emerald-400" />
                <span>Step 1: Create Secure Login</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Set up your email and password to access online banking.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
              <input
                type="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
              <input
                type="password"
                required
                minLength={6}
                placeholder="Minimum 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Confirm Password</label>
              <input
                type="password"
                required
                placeholder="Re-enter your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <button
              type="button"
              onClick={handleNext}
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 font-semibold rounded-xl text-sm transition mt-6 flex items-center justify-center space-x-1"
            >
              <span>Continue to Personal Info</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* STEP 2: PERSONAL INFORMATION */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="border-b border-slate-700/60 pb-3 mb-4">
              <h3 className="font-semibold text-slate-200 text-sm flex items-center space-x-2">
                <User className="w-4 h-4 text-emerald-400" />
                <span>Step 2: Personal Details</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Provide your legal identity information as per official records.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Full Legal Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Rahul Sharma"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Gender</label>
              <div className="grid grid-cols-3 gap-3">
                {(['MALE', 'FEMALE', 'OTHER'] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGender(g)}
                    className={`py-2 px-3 text-xs font-semibold rounded-xl border transition ${
                      gender === g
                        ? 'bg-emerald-600/30 border-emerald-500 text-emerald-300'
                        : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-600'
                    }`}
                  >
                    {g === 'MALE' ? 'Male' : g === 'FEMALE' ? 'Female' : 'Other'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Date of Birth</label>
              <input
                type="date"
                required
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="flex space-x-3 pt-4">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="py-3 px-4 bg-slate-700 hover:bg-slate-600 font-semibold rounded-xl text-sm transition flex items-center justify-center space-x-1"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
              <button
                type="button"
                onClick={handleNext}
                className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 font-semibold rounded-xl text-sm transition flex items-center justify-center space-x-1"
              >
                <span>Continue to KYC</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: KYC DOCUMENTS */}
        {step === 3 && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="border-b border-slate-700/60 pb-3 mb-4">
              <h3 className="font-semibold text-slate-200 text-sm flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Step 3: Identity Verification (KYC)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Enter your Aadhaar and PAN numbers to complete account verification.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Aadhaar Number (12 Digits)
              </label>
              <input
                type="text"
                required
                maxLength={12}
                placeholder="123456789012"
                value={aadhaarNo}
                onChange={(e) => setAadhaarNo(e.target.value.replace(/\D/g, ''))}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white font-mono tracking-wider focus:outline-none focus:border-emerald-500"
              />
              <span className="text-[11px] text-slate-400 mt-0.5 block">
                {aadhaarNo.length}/12 digits
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                PAN Card Number (10 Characters)
              </label>
              <input
                type="text"
                required
                maxLength={10}
                placeholder="ABCDE1234F"
                value={panNo}
                onChange={(e) => setPanNo(e.target.value.toUpperCase())}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-white font-mono tracking-wider uppercase focus:outline-none focus:border-emerald-500"
              />
              <span className="text-[11px] text-slate-400 mt-0.5 block">Format: ABCDE1234F</span>
            </div>

            <div className="pt-2">
              <label className="flex items-start space-x-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreedTerms}
                  onChange={(e) => setAgreedTerms(e.target.checked)}
                  className="mt-1 rounded bg-slate-900 border-slate-700 text-emerald-500 focus:ring-0"
                />
                <span className="text-xs text-slate-300 leading-relaxed">
                  I certify that the personal details, Aadhaar, and PAN provided above are correct and belong to me.
                </span>
              </label>
            </div>

            <div className="flex space-x-3 pt-4">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="py-3 px-4 bg-slate-700 hover:bg-slate-600 font-semibold rounded-xl text-sm transition flex items-center justify-center space-x-1"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 font-semibold rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-900/30"
              >
                {loading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Open Account & Seed ₹10,000</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        <div className="mt-6 text-center text-xs text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="text-emerald-400 hover:underline">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}

// Notifications Page
function BankNotificationsPage() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ id: string; msg: string; type: 'success' | 'error' } | null>(
    null
  );

  const loadNotifications = async () => {
    try {
      const res = await bankNotificationsApi.getNotifications();
      setNotifications(res);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const handleApprove = async (notif: any) => {
    if (!notif.reference_id) return;
    setActionLoading(notif.id);
    try {
      const res = await bankLinkingApi.approveRequest(notif.reference_id);
      setActionMessage({
        id: notif.id,
        msg: `Link Approved! MiniPay account successfully authorized.`,
        type: 'success',
      });
      loadNotifications();
    } catch (err: any) {
      setActionMessage({
        id: notif.id,
        msg: err.detail || 'Approval failed',
        type: 'error',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeny = async (notif: any) => {
    if (!notif.reference_id) return;
    if (!confirm('Are you sure you want to deny this link request?')) return;
    setActionLoading(notif.id);
    try {
      await bankLinkingApi.denyRequest(notif.reference_id);
      setActionMessage({
        id: notif.id,
        msg: `Link request denied.`,
        type: 'success',
      });
      loadNotifications();
    } catch (err: any) {
      setActionMessage({
        id: notif.id,
        msg: err.detail || 'Denial failed',
        type: 'error',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await bankNotificationsApi.markAsRead(id);
      loadNotifications();
    } catch {}
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 flex items-center space-x-2">
            <Bell className="w-6 h-6 text-emerald-600" />
            <span>Bank Notifications</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Review incoming third-party authorization requests and account security alerts.
          </p>
        </div>
        <button
          onClick={loadNotifications}
          className="text-xs font-semibold px-3 py-1.5 bg-slate-200 hover:bg-slate-300 rounded-lg text-slate-700 flex items-center space-x-1"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="p-12 text-center text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-500" />
          <p className="text-sm">Loading notifications...</p>
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 shadow-sm">
          <Bell className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="font-bold text-slate-700">No Notifications</h3>
          <p className="text-xs text-slate-400 mt-1">You are all caught up! No pending requests.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`bg-white rounded-2xl p-6 border transition shadow-sm ${
                !n.is_read ? 'border-emerald-300 ring-2 ring-emerald-500/10' : 'border-slate-200'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900 text-base">{n.title}</span>
                    {!n.is_read && (
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full uppercase">
                        New
                      </span>
                    )}
                    <span
                      className={`px-2 py-0.5 text-[10px] font-bold rounded-full uppercase ${
                        n.status === 'APPROVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : n.status === 'DENIED'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {n.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed pt-1">{n.message}</p>
                  <div className="text-xs text-slate-400 pt-2 flex items-center space-x-3">
                    <span>{new Date(n.created_at).toLocaleString()}</span>
                    {n.reference_id && (
                      <span className="font-mono text-[11px] text-slate-400">Ref: {n.reference_id}</span>
                    )}
                  </div>
                </div>

                {!n.is_read && !n.is_actionable && (
                  <button
                    onClick={() => handleMarkRead(n.id)}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-800 border border-slate-200 px-2.5 py-1 rounded-lg"
                  >
                    Mark read
                  </button>
                )}
              </div>

              {actionMessage && actionMessage.id === n.id && (
                <div
                  className={`mt-4 p-3 rounded-xl text-xs font-medium ${
                    actionMessage.type === 'success'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-red-50 text-red-800 border border-red-200'
                  }`}
                >
                  {actionMessage.msg}
                </div>
              )}

              {/* ACTIONABLE LINK REQUEST BUTTONS */}
              {n.is_actionable && n.status === 'PENDING' && (
                <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-end space-x-3">
                  <button
                    onClick={() => handleDeny(n)}
                    disabled={actionLoading === n.id}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition"
                  >
                    Deny
                  </button>
                  <button
                    onClick={() => handleApprove(n)}
                    disabled={actionLoading === n.id}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition flex items-center space-x-1.5 shadow-sm shadow-emerald-600/30"
                  >
                    {actionLoading === n.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Approve Access</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Dashboard
function BankDashboardPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [selectedAcc, setSelectedAcc] = useState<string>('');
  const [txns, setTxns] = useState<any[]>([]);

  useEffect(() => {
    bankAccountsApi.getAccounts().then((res) => {
      setAccounts(res);
      if (res.length > 0) {
        setSelectedAcc(res[0].account_no);
      }
    });
  }, []);

  useEffect(() => {
    if (selectedAcc) {
      bankAccountsApi.getTransactions(selectedAcc).then(setTxns);
    }
  }, [selectedAcc]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accounts.map((acc) => (
          <div
            key={acc.id}
            className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex justify-between items-center"
          >
            <div>
              <div className="text-xs text-slate-500 font-semibold">Account Number</div>
              <div className="text-lg font-bold text-slate-900 font-mono">{acc.account_no}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-slate-500 font-semibold">Current Balance</div>
              <div className="text-2xl font-extrabold text-emerald-600">₹{(acc.balance / 100).toFixed(2)}</div>
              <div className="text-xs text-slate-400">({acc.balance} paise)</div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h3 className="text-lg font-bold text-slate-900 mb-4">Bank Account Activity</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
                <th className="px-4 py-3">Reference ID</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {txns.map((t) => (
                <tr key={t.id}>
                  <td className="px-4 py-3 font-mono text-xs">{t.reference_id}</td>
                  <td className="px-4 py-3 font-semibold">{t.type}</td>
                  <td className="px-4 py-3 font-bold">₹{(t.amount / 100).toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        t.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{new Date(t.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// OAuth Consent Screen (Legacy / Direct redirect flow)
function BankConsentScreenPage() {
  const { user } = useBankAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [selectedAcc, setSelectedAcc] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const query = new URLSearchParams(location.search);
  const paypalRequestId = query.get('paypal_request_id') || '';
  const bankId = query.get('bank_id') || 'bank_x';

  if (!user) {
    return <Navigate to={`/login?returnUrl=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  useEffect(() => {
    bankAccountsApi.getAccounts().then((res) => {
      setAccounts(res);
      if (res.length > 0) setSelectedAcc(res[0].account_no);
    });
  }, []);

  const handleApprove = async () => {
    setLoading(true);
    try {
      const res = await bankLinkingApi.approveConsent(selectedAcc, paypalRequestId);
      window.location.href = `${PAYPAL_URL}/funding/callback?code=${res.authorization_code}&bank_id=${bankId}&paypal_request_id=${paypalRequestId}`;
    } catch (err: any) {
      alert(err.detail || 'Consent approval failed');
      setLoading(false);
    }
  };

  const handleDeny = () => {
    window.location.href = `${PAYPAL_URL}/funding?error=user_denied`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="max-w-lg w-full bg-slate-800 rounded-2xl p-8 border border-slate-700 text-white space-y-6">
        <div className="flex items-center space-x-3 border-b border-slate-700 pb-4">
          <ShieldCheck className="w-8 h-8 text-emerald-400" />
          <div>
            <h2 className="text-xl font-bold">Authorize MiniPay Access</h2>
            <p className="text-xs text-slate-400">{BANK_NAME} OAuth 2.0 Consent Screen</p>
          </div>
        </div>

        <div className="bg-slate-900 p-4 rounded-xl space-y-2 text-sm">
          <p className="text-slate-300">
            <strong>MiniPay</strong> is requesting permission to link to your bank account for:
          </p>
          <ul className="text-xs text-slate-400 list-disc list-inside space-y-1">
            <li>Debiting your account for wallet top-ups and bank-funded P2P payments</li>
            <li>Crediting your account upon wallet withdrawals</li>
            <li>Per-transaction debit limit up to ₹50,000</li>
          </ul>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-2">Select Bank Account</label>
          <select
            value={selectedAcc}
            onChange={(e) => setSelectedAcc(e.target.value)}
            className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white"
          >
            {accounts.map((acc) => (
              <option key={acc.id} value={acc.account_no}>
                {acc.account_no} (Balance: ₹{(acc.balance / 100).toFixed(2)})
              </option>
            ))}
          </select>
        </div>

        <div className="flex space-x-3 pt-4">
          <button
            onClick={handleDeny}
            className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-semibold transition"
          >
            Deny
          </button>
          <button
            onClick={handleApprove}
            disabled={loading}
            className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-semibold transition flex items-center justify-center space-x-2"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Authorize Access</span>}
          </button>
        </div>
      </div>
    </div>
  );
}

// Consents Management
function BankConsentsPage() {
  const [consents, setConsents] = useState<any[]>([]);

  const load = async () => {
    const res = await bankLinkingApi.getConsents();
    setConsents(res);
  };

  useEffect(() => {
    load();
  }, []);

  const handleRevoke = async (consentId: string) => {
    if (confirm('Revoke access for this token?')) {
      await bankLinkingApi.revokeConsent(consentId);
      load();
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <h3 className="text-xl font-bold text-slate-900">Active Third-Party Consents (MiniPay)</h3>
      <div className="space-y-3">
        {consents.map((c) => (
          <div
            key={c.id}
            className="bg-white p-4 rounded-xl border border-slate-200 flex justify-between items-center shadow-sm"
          >
            <div>
              <div className="font-bold text-slate-900">MiniPay Payment App</div>
              <div className="text-xs text-slate-500">
                Account: {c.masked_account} | Limit: ₹{(c.per_txn_limit / 100).toFixed(2)}
              </div>
              <div className="text-xs text-slate-400 font-mono">Consent ID: {c.consent_id}</div>
            </div>

            <div className="flex items-center space-x-3">
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  c.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                }`}
              >
                {c.status}
              </span>
              {c.status === 'ACTIVE' && (
                <button
                  onClick={() => handleRevoke(c.consent_id)}
                  className="text-xs font-semibold text-red-600 hover:underline"
                >
                  Revoke Token
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BankProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useBankAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function BankApp() {
  return (
    <BankAuthProvider>
      <Router>
        <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
          <BankNavbar />
          <main className="flex-1">
            <Routes>
              <Route path="/login" element={<BankLoginPage />} />
              <Route path="/register" element={<BankRegisterPage />} />
              <Route path="/" element={<BankProtectedRoute><BankDashboardPage /></BankProtectedRoute>} />
              <Route path="/consent" element={<BankConsentScreenPage />} />
              <Route path="/consents" element={<BankProtectedRoute><BankConsentsPage /></BankProtectedRoute>} />
              <Route path="/notifications" element={<BankProtectedRoute><BankNotificationsPage /></BankProtectedRoute>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </Router>
    </BankAuthProvider>
  );
}
