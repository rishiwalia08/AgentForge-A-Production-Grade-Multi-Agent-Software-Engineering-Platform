'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const { login, loading } = useAuth();
  const [mockToken, setMockToken] = useState('mock_token_rishi');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (tokenValue: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await login(tokenValue);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check backend connection.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-zinc-950">
        <div className="w-12 h-12 rounded-full border-4 border-violet-500 border-t-transparent animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 p-4 relative overflow-hidden">
      {/* Decorative Gradients */}
      <div className="absolute top-1/4 left-1/4 w-[300px] h-[300px] bg-violet-600/10 rounded-full filter blur-[80px]"></div>
      <div className="absolute bottom-1/4 right-1/4 w-[250px] h-[250px] bg-emerald-600/10 rounded-full filter blur-[80px]"></div>

      <div className="w-full max-w-md bg-zinc-900/60 backdrop-blur-md border border-zinc-800 rounded-2xl p-8 shadow-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-tr from-violet-600 to-indigo-500 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/25 mb-4">
            {/* SVG Logo */}
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-400">
            Antigravity Workspace
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Multi-Agent Development & RAG Engine</p>
        </div>

        {error && (
          <div className="bg-red-950/50 border border-red-900/80 rounded-xl p-4 mb-6 text-sm text-red-400 flex gap-2">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-4">
          {/* Main Provider Button */}
          <button
            onClick={() => handleLogin("mock_token_rishi")}
            disabled={submitting}
            className="w-full flex items-center justify-center gap-3 bg-white text-zinc-950 hover:bg-zinc-200 transition-colors font-medium rounded-xl py-3 text-sm shadow-md"
          >
            {/* Google Icon SVG */}
            <svg className="w-5 h-5" viewBox="0 0 24 24" width="24" height="24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            <span>Sign in with Google</span>
          </button>

          {/* Divider */}
          <div className="flex items-center my-6">
            <div className="flex-grow border-t border-zinc-800"></div>
            <span className="text-zinc-600 text-xs px-3 font-medium uppercase tracking-wider">Local Mock Auth</span>
            <div className="flex-grow border-t border-zinc-800"></div>
          </div>

          {/* Mock Auth Panel */}
          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-4 space-y-3">
            <label className="block text-zinc-500 text-xs font-semibold">MOCK TOKEN VALUE</label>
            <input
              type="text"
              value={mockToken}
              onChange={(e) => setMockToken(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-2 px-3 text-sm text-zinc-200 focus:outline-none focus:border-violet-600"
              placeholder="mock_token_username"
            />
            <button
              onClick={() => handleLogin(mockToken)}
              disabled={submitting || !mockToken}
              className="w-full bg-violet-600 hover:bg-violet-500 text-white font-medium py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
            >
              {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
              <span>Mock Sign In</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
