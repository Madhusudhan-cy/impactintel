import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, AlertCircle, ArrowRight } from 'lucide-react';

export default function GitHubCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = searchParams.get('token');
    const err = searchParams.get('error');
    const code = searchParams.get('code');

    if (err) {
      setError(decodeURIComponent(err));
      return;
    }

    if (token) {
      loginWithToken(token);
      navigate('/repositories', { replace: true });
      return;
    }

    if (code) {
      if (import.meta.env.VITE_ENABLE_DEV_BYPASS === 'true') {
        loginWithToken('dev_mock_jwt_token_2026');
        navigate('/repositories', { replace: true });
        return;
      }
      setError('Direct authorization code received on frontend without token exchange. Please authenticate through backend flow.');
      return;
    }

    setError('Authentication incomplete: no session token received from GitHub.');
  }, [searchParams, loginWithToken, navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-[#F5FAFA] flex items-center justify-center p-6 text-[#172B35]">
        <div className="max-w-md w-full p-6 rounded-xl bg-white border border-rose-200 shadow-card text-center">
          <div className="w-10 h-10 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3 border border-rose-100">
            <AlertCircle className="w-5 h-5" />
          </div>
          <h2 className="text-base font-bold text-[#172B35] mb-1.5">Authentication Failed</h2>
          <p className="text-xs text-[#6B818B] mb-5">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="w-full inline-flex items-center justify-center gap-2 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all"
          >
            <span>Back to Home</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5FAFA] flex flex-col items-center justify-center text-[#172B35]">
      <Loader2 className="w-7 h-7 text-[#16B89A] animate-spin mb-3" />
      <div className="text-xs font-semibold text-[#172B35]">Authenticating with GitHub...</div>
      <div className="text-[11px] text-[#6B818B] font-mono mt-0.5">Establishing secure session</div>
    </div>
  );
}
