'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getMemoryItems, MemoryItem } from '@/lib/api';

export default function MemoryViewerPage() {
  const router = useRouter();
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetchMemories();
  }, []);

  const fetchMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await getMemoryItems();
      setMemories(items);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve memory items.');
    } finally {
      setLoading(false);
    }
  };

  const filteredMemories = memories.filter((m) => {
    if (filter === 'all') return true;
    return m.kind.toLowerCase() === filter.toLowerCase();
  });

  // Extract unique kinds for filtering
  const kinds = Array.from(new Set(memories.map((m) => m.kind.toLowerCase())));

  return (
    <div className="min-h-screen bg-zinc-950 p-6 md:p-12 text-zinc-50 relative">
      <div className="absolute top-10 left-10 w-96 h-96 bg-violet-600/5 rounded-full filter blur-[100px] pointer-events-none"></div>

      <div className="max-w-5xl mx-auto space-y-8 relative z-10">
        
        {/* Header */}
        <header className="flex items-center justify-between border-b border-zinc-800 pb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/projects')}
              className="text-zinc-400 hover:text-white p-1 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </button>
            <div className="h-5 w-px bg-zinc-800"></div>
            <div>
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-400">
                Memory Debugger
              </h1>
              <p className="text-xs text-zinc-500">Inspect experiences, AST codebase knowledge, and semantic vectors.</p>
            </div>
          </div>

          <button
            onClick={fetchMemories}
            className="text-xs bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:text-white px-4 py-2 rounded-xl transition-colors"
          >
            Refresh Logs
          </button>
        </header>

        {/* Error Notification */}
        {error && (
          <div className="bg-red-950/40 border border-red-900/60 rounded-xl p-4 text-sm text-red-400 flex gap-2">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          <button
            onClick={() => setFilter('all')}
            className={`text-xs px-4 py-2 rounded-xl border font-semibold capitalize transition-colors ${
              filter === 'all'
                ? 'bg-violet-600 border-violet-500 text-white'
                : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            All Memories ({memories.length})
          </button>
          {kinds.map((kind) => (
            <button
              key={kind}
              onClick={() => setFilter(kind)}
              className={`text-xs px-4 py-2 rounded-xl border font-semibold capitalize transition-colors ${
                filter === kind
                  ? 'bg-violet-600 border-violet-500 text-white'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {kind} ({memories.filter((m) => m.kind.toLowerCase() === kind).length})
            </button>
          ))}
        </div>

        {/* Memory Grid */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-zinc-900/40 border border-zinc-800 rounded-xl h-24 animate-pulse animate-shimmer"></div>
            ))}
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="flex flex-col items-center justify-center border border-dashed border-zinc-800 rounded-2xl p-16 text-center bg-zinc-900/10">
            <h3 className="text-base font-semibold text-zinc-300">No memory logs recorded</h3>
            <p className="text-zinc-500 text-xs mt-1">Submit run executions to let the reflection agents register memory points.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredMemories.map((memory) => (
              <div
                key={memory.id}
                className="bg-zinc-900/30 border border-zinc-900 hover:border-zinc-800/80 rounded-xl p-6 transition-colors space-y-4"
              >
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="bg-violet-950/80 text-violet-400 border border-violet-900/50 text-[10px] font-bold font-mono px-2 py-0.5 rounded-full uppercase">
                      {memory.kind}
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">ID: {memory.id}</span>
                  </div>
                  <span className="text-[10px] text-zinc-600 font-mono">
                    {new Date(memory.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div className="text-zinc-300 leading-relaxed whitespace-pre-wrap">{memory.content}</div>

                  {memory.metadata_json && Object.keys(memory.metadata_json).length > 0 && (
                    <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-900 text-[10px] text-zinc-500 space-y-1">
                      <div className="font-bold text-[9px] uppercase tracking-wider text-zinc-600 mb-1">Metadata Attributes</div>
                      {Object.entries(memory.metadata_json).map(([k, v]) => (
                        <div key={k} className="flex gap-2">
                          <span className="text-zinc-600 font-semibold">{k}:</span>
                          <span className="text-zinc-400 truncate">{JSON.stringify(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
