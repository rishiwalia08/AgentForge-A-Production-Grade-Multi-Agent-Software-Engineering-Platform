'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createRun } from '@/lib/api';

function WorkspaceContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get('project');
  const [task, setTask] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !task.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await createRun(projectId, task);
      router.push(`/runs/${res.run_id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to initialize agent run');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 relative">
      <div className="absolute top-1/4 left-1/4 w-[300px] h-[300px] bg-violet-600/5 rounded-full filter blur-[80px] pointer-events-none"></div>
      
      <div className="w-full max-w-xl bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 backdrop-blur-md relative z-10 shadow-2xl space-y-6">
        <div className="space-y-1">
          <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-400">
            Launch Agent Workspace
          </h2>
          <p className="text-zinc-500 text-sm">Submit a coding goal or prompt to compile and execute the LangGraph multi-agent swarm.</p>
        </div>

        {error && (
          <div className="bg-red-950/40 border border-red-900/60 rounded-xl p-4 text-sm text-red-400 flex gap-2">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Goal Instruction</label>
            <textarea
              required
              rows={5}
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-3 px-4 text-sm text-zinc-200 focus:outline-none focus:border-violet-600 focus:ring-1 focus:ring-violet-600/50 resize-none h-40 font-mono"
              placeholder="e.g. Build an authentication system using PyJWT in backend/app/core/auth.py. Verify token signatures and add tests."
            />
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={() => router.push('/projects')}
              className="bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 px-5 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !task.trim()}
              className="bg-violet-600 hover:bg-violet-500 text-white font-medium px-6 py-2.5 rounded-xl text-sm transition-colors flex items-center gap-2 shadow-lg shadow-violet-600/20"
            >
              {loading && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
              <span>Compile & Run Swarm</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function WorkspacePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border-4 border-violet-500 border-t-transparent animate-spin"></div>
      </div>
    }>
      <WorkspaceContent />
    </Suspense>
  );
}
