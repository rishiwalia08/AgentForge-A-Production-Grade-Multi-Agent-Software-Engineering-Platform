'use client';

import { useAuth } from '@/lib/auth';

export default function Home() {
  const { loading } = useAuth();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-zinc-950 text-zinc-50">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-violet-500 border-t-transparent animate-spin"></div>
        <p className="text-zinc-400 text-sm animate-pulse">Initializing Antigravity Workspace...</p>
      </div>
    </div>
  );
}
