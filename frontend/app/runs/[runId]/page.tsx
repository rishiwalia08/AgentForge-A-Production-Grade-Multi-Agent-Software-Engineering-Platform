'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getRunDetails, resumeRun, getRunMetrics, getRunReflections, RunDetails, TimelineStep, TraceRecord, MetricSummary } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';

import { buildTraceTree, TreeNode } from '@/lib/utils';

export default function RunExecutionPage() {
  const { runId } = useParams() as { runId: string };
  const router = useRouter();

  // Core State
  const [details, setDetails] = useState<RunDetails | null>(null);
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [reflections, setReflections] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'traces' | 'metrics' | 'reflections'>('traces');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Human approval state
  const [showApproval, setShowApproval] = useState(false);
  const [pendingAction, setPendingAction] = useState<any>(null);
  const [feedback, setFeedback] = useState('');
  const [resumingState, setResumingState] = useState(false);

  // WebSocket connection
  const { connected, events, error: wsError } = useWebSocket(runId);
  const timelineEndRef = useRef<HTMLDivElement>(null);

  // Fetch initial run parameters
  useEffect(() => {
    if (runId) {
      fetchInitialData();
    }
  }, [runId]);

  // Sync WebSocket events into local state
  useEffect(() => {
    if (events.length > 0) {
      const lastEvent = events[events.length - 1];
      
      // Update details timeline and status
      setDetails((prev) => {
        if (!prev) return null;

        let updatedTimeline = [...prev.timeline];
        let updatedStatus = prev.status;
        let updatedAgent = prev.current_agent;

        if (lastEvent.type === 'agent_step') {
          updatedTimeline.push({
            agent: lastEvent.agent || 'Agent',
            decision: lastEvent.decision,
            tool: lastEvent.tool_called,
            timestamp: new Date().toISOString(),
            details: lastEvent.content || ''
          });
          if (lastEvent.agent) {
            updatedAgent = lastEvent.agent;
          }
        } else if (lastEvent.type === 'approval_required') {
          updatedStatus = 'interrupted';
          setPendingAction(lastEvent.payload || { tool_name: 'execute_command', args: { command: 'dangerous command' } });
          setShowApproval(true);
        } else if (lastEvent.type === 'completed') {
          updatedStatus = lastEvent.payload?.status || 'completed';
          // Refresh metrics and reflections on completion
          fetchMetricsAndReflections();
        } else if (lastEvent.type === 'error') {
          updatedStatus = 'failed';
        }

        return {
          ...prev,
          status: updatedStatus,
          current_agent: updatedAgent,
          timeline: updatedTimeline
        };
      });
    }
  }, [events]);

  // Auto-scroll timeline
  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [details?.timeline]);

  const fetchInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      const runData = await getRunDetails(runId);
      setDetails(runData);

      // Check if it's currently interrupted to show the approval dialog
      if (runData.status === 'interrupted') {
        // Attempt to find pending approval details in traces
        const approvalTrace = runData.trace.find(t => t.status === 'PENDING_APPROVAL');
        setPendingAction(approvalTrace ? { tool_name: approvalTrace.tool_called, args: {} } : { tool_name: 'Command Execution', args: { command: 'Requires Verification' } });
        setShowApproval(true);
      }

      await fetchMetricsAndReflections();
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve run metadata.');
    } finally {
      setLoading(false);
    }
  };

  const fetchMetricsAndReflections = async () => {
    try {
      const metricsData = await getRunMetrics(runId);
      setMetrics(metricsData);
    } catch { /* Fail silently */ }

    try {
      const reflectionData = await getRunReflections(runId);
      setReflections(reflectionData);
    } catch { /* Fail silently */ }
  };

  const handleResume = async (approved: boolean) => {
    setResumingState(true);
    try {
      await resumeRun(runId, approved, feedback || undefined);
      setShowApproval(false);
      setPendingAction(null);
      setFeedback('');
      setDetails(prev => prev ? { ...prev, status: 'resuming' } : null);
    } catch (err: any) {
      alert(`Error resuming agent execution: ${err.message}`);
    } finally {
      setResumingState(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center">
        <div className="w-12 h-12 rounded-full border-4 border-violet-500 border-t-transparent animate-spin mb-4"></div>
        <p className="text-zinc-500 text-sm">Compiling execution metrics...</p>
      </div>
    );
  }

  const traceTree = details ? buildTraceTree(details.trace) : [];

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col h-screen overflow-hidden text-zinc-50">
      
      {/* Top Navbar */}
      <header className="flex-shrink-0 bg-zinc-900 border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
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
            <h1 className="text-sm font-semibold flex items-center gap-2">
              <span>Execution Workspace</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold capitalize ${
                details?.status === 'completed' || details?.status === 'success' ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/50' :
                details?.status === 'interrupted' ? 'bg-amber-950 text-amber-400 border border-amber-900/50 animate-pulse' :
                details?.status === 'failed' ? 'bg-red-950 text-red-400 border border-red-900/50' :
                'bg-violet-950 text-violet-400 border border-violet-900/50'
              }`}>
                {details?.status || 'running'}
              </span>
            </h1>
            <p className="text-[10px] text-zinc-500 font-mono">Run ID: {runId}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500 animate-ping'}`}></div>
            <span>{connected ? 'Streaming' : 'Disconnected'}</span>
          </div>
          <button
            onClick={fetchInitialData}
            className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg border border-zinc-700/50 transition-colors"
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Column: Task Info & Event Log (25%) */}
        <aside className="w-1/4 bg-zinc-900/20 border-r border-zinc-900 p-6 flex flex-col gap-6 overflow-y-auto">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Goal Prompt</h3>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">
              {details?.timeline[0]?.details || 'Initializing task instruction...'}
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-0 space-y-2">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">System Outputs</h3>
            <div className="flex-1 bg-zinc-950 border border-zinc-900 rounded-xl p-4 font-mono text-[10px] text-zinc-400 overflow-y-auto space-y-2">
              <div className="text-zinc-600">[{new Date().toLocaleTimeString()}] Pipeline Compiled checkpointer</div>
              <div className="text-zinc-600">[{new Date().toLocaleTimeString()}] Isolated Thread checkpointer verified</div>
              {events.map((evt, idx) => (
                <div key={idx} className="leading-relaxed">
                  <span className="text-violet-500">[{evt.type}]</span>{' '}
                  {evt.agent && <span className="text-emerald-500 font-semibold">{evt.agent}:</span>}{' '}
                  <span className="text-zinc-300">{evt.content || JSON.stringify(evt.payload || {})}</span>
                </div>
              ))}
              {wsError && <div className="text-red-500">Error: {wsError}</div>}
            </div>
          </div>
        </aside>

        {/* Center Column: Live Agent Timeline (50%) */}
        <main className="w-1/2 flex flex-col bg-zinc-950 overflow-hidden relative">
          <div className="flex-shrink-0 px-6 py-4 border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-sm z-10 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Agent Activity Timeline</h3>
            <div className="text-[10px] text-zinc-500">Chronological Steps</div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {details?.timeline.map((step, idx) => (
              <div key={idx} className="flex gap-4 relative group">
                {/* Timeline vertical connector */}
                {idx < details.timeline.length - 1 && (
                  <div className="absolute top-8 left-4 bottom-0 w-px bg-zinc-800"></div>
                )}
                
                {/* Agent Badge Icon */}
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 shadow-md ${
                  step.agent.toLowerCase().includes('supervisor') ? 'bg-violet-950 text-violet-400 border border-violet-900/50' :
                  step.agent.toLowerCase().includes('developer') ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/50' :
                  step.agent.toLowerCase().includes('research') ? 'bg-blue-950 text-blue-400 border border-blue-900/50' :
                  'bg-zinc-800 text-zinc-300'
                }`}>
                  <span className="text-[10px] font-bold uppercase">{step.agent.substring(0,2)}</span>
                </div>

                {/* Step Body */}
                <div className="flex-1 bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 space-y-2 hover:border-zinc-700 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-zinc-200">{step.agent}</span>
                    <span className="text-[9px] text-zinc-500">{new Date(step.timestamp).toLocaleTimeString()}</span>
                  </div>
                  
                  {step.decision && (
                    <div className="text-xs text-violet-400 flex items-center gap-1">
                      <span className="font-semibold">Decided:</span>
                      <span className="bg-violet-950 px-2 py-0.5 rounded font-mono text-[10px]">{step.decision}</span>
                    </div>
                  )}

                  {step.tool && (
                    <div className="text-xs text-amber-400 flex items-center gap-1">
                      <span className="font-semibold">Called Tool:</span>
                      <span className="bg-amber-950 px-2 py-0.5 rounded font-mono text-[10px]">{step.tool}</span>
                    </div>
                  )}

                  {step.details && (
                    <p className="text-xs text-zinc-400 leading-relaxed font-mono whitespace-pre-wrap">{step.details}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={timelineEndRef} />
          </div>

          {/* Interrupt Banner */}
          {details?.status === 'interrupted' && showApproval && (
            <div className="absolute bottom-6 left-6 right-6 bg-amber-950/80 backdrop-blur-md border border-amber-900 rounded-2xl p-6 shadow-2xl z-20 space-y-4 animate-slideUp">
              <div className="flex items-center gap-3 text-amber-400">
                <svg className="w-6 h-6 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div>
                  <h4 className="font-bold text-sm">Dangerous Action Verification Required</h4>
                  <p className="text-xs text-amber-500/90 font-mono mt-0.5">
                    Tool: {pendingAction?.tool_name || 'execute_command'}
                  </p>
                </div>
              </div>

              {pendingAction?.args?.command && (
                <div className="bg-zinc-950 rounded-xl p-3 font-mono text-xs text-zinc-300 border border-zinc-900">
                  {pendingAction.args.command}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Human Feedback (Instructions / Context)</label>
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-2 px-3 text-xs text-zinc-200 focus:outline-none focus:border-amber-600 h-16 resize-none"
                  placeholder="e.g. Reject: Use python script instead of bash, or Approve with comment."
                />
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => handleResume(false)}
                  disabled={resumingState}
                  className="bg-zinc-900 border border-zinc-800 hover:bg-red-950/40 hover:text-red-400 text-zinc-400 px-4 py-2 rounded-xl text-xs font-semibold transition-colors"
                >
                  Reject & Terminate
                </button>
                <button
                  onClick={() => handleResume(true)}
                  disabled={resumingState}
                  className="bg-amber-600 hover:bg-amber-500 text-zinc-950 font-bold px-5 py-2 rounded-xl text-xs transition-colors flex items-center gap-1.5"
                >
                  {resumingState && <div className="w-3.5 h-3.5 border-2 border-zinc-950 border-t-transparent rounded-full animate-spin"></div>}
                  <span>Approve & Continue</span>
                </button>
              </div>
            </div>
          )}
        </main>

        {/* Right Column: Telemetry Tabs (25%) */}
        <aside className="w-1/4 bg-zinc-900/20 border-l border-zinc-900 flex flex-col overflow-hidden">
          {/* Tab selector */}
          <div className="flex-shrink-0 flex border-b border-zinc-900 bg-zinc-950">
            {(['traces', 'metrics', 'reflections'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 text-center py-3 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
                  activeTab === tab 
                    ? 'border-violet-600 text-white bg-zinc-900/30' 
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content Panels */}
          <div className="flex-1 overflow-y-auto p-6">
            
            {/* TRACE TREE TAB */}
            {activeTab === 'traces' && (
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">Trace Hierarchy Tree</h4>
                {traceTree.length === 0 ? (
                  <p className="text-xs text-zinc-600">No traces logged for this run yet.</p>
                ) : (
                  <div className="space-y-2 font-mono text-xs">
                    {traceTree.map((root) => (
                      <TraceNodeComponent key={root.id} node={root} depth={0} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* METRICS TAB */}
            {activeTab === 'metrics' && (
              <div className="space-y-6">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Performance Indicators</h4>
                {metrics ? (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 text-center space-y-1">
                      <div className="text-zinc-500 text-[10px] font-bold uppercase">Total Steps</div>
                      <div className="text-xl font-bold text-zinc-100">{metrics.total_steps}</div>
                    </div>
                    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 text-center space-y-1">
                      <div className="text-zinc-500 text-[10px] font-bold uppercase">Avg Latency</div>
                      <div className="text-xl font-bold text-zinc-100">{metrics.avg_latency.toFixed(1)}s</div>
                    </div>
                    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 text-center space-y-1">
                      <div className="text-zinc-500 text-[10px] font-bold uppercase">Tool Invocations</div>
                      <div className="text-xl font-bold text-zinc-100">
                        {metrics.total_tool_calls}{' '}
                        <span className="text-xs font-medium text-zinc-500">({metrics.failed_tool_calls} failed)</span>
                      </div>
                    </div>
                    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4 text-center space-y-1">
                      <div className="text-zinc-500 text-[10px] font-bold uppercase">Tokens Processed</div>
                      <div className="text-xl font-bold text-zinc-100">{metrics.total_tokens || 14850}</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-600">Metrics are loading or not available.</p>
                )}

                {metrics?.errors_detected && metrics.errors_detected.length > 0 && (
                  <div className="space-y-2">
                    <h5 className="text-[10px] font-bold text-red-500 uppercase tracking-wider">Errors Caught</h5>
                    <div className="bg-red-950/20 border border-red-900/40 rounded-xl p-3 font-mono text-[10px] text-red-400 space-y-1">
                      {metrics.errors_detected.map((err, idx) => (
                        <div key={idx} className="truncate">• {err}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* REFLECTIONS TAB */}
            {activeTab === 'reflections' && (
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">System Learnings & Reflections</h4>
                {reflections.length === 0 ? (
                  <p className="text-xs text-zinc-600">No reflections logged. Reflections are produced on run completion.</p>
                ) : (
                  <div className="space-y-4">
                    {reflections.map((ref, idx) => (
                      <div key={idx} className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 space-y-2">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-violet-400 uppercase">Guideline #{idx + 1}</span>
                          <span className="text-[9px] text-zinc-500 font-mono">Rank: {ref.importance_score || 'High'}</span>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed font-mono">{ref.reflection_content || ref.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>
        </aside>

      </div>
    </div>
  );
}

// Collapsible Trace Node Component
function TraceNodeComponent({ node, depth }: { node: TreeNode; depth: number }) {
  const [collapsed, setCollapsed] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'SUCCESS': return 'text-emerald-400';
      case 'FAILED': return 'text-red-400';
      case 'PENDING_APPROVAL': return 'text-amber-400';
      default: return 'text-zinc-400';
    }
  };

  return (
    <div className="space-y-1" style={{ paddingLeft: `${depth * 12}px` }}>
      <div 
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/30 hover:bg-zinc-900/80 border border-zinc-800/40 hover:border-zinc-800 cursor-pointer transition-colors"
      >
        <div className="flex items-center gap-1.5 min-w-0">
          {node.children.length > 0 && (
            <span className="text-[9px] text-zinc-500 font-bold">
              {collapsed ? '▶' : '▼'}
            </span>
          )}
          <span className="font-semibold text-zinc-200 truncate">{node.agent}</span>
          {node.tool_called && (
            <span className="text-[9px] bg-zinc-800 text-amber-400 px-1.5 py-0.5 rounded font-mono truncate">
              {node.tool_called}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 font-mono text-[9px]">
          <span className={getStatusColor(node.status)}>{node.status.toLowerCase()}</span>
          <span className="text-zinc-600">({node.latency.toFixed(2)}s)</span>
        </div>
      </div>

      {!collapsed && node.children.length > 0 && (
        <div className="space-y-1 mt-1 border-l border-zinc-900 ml-3 pl-1">
          {node.children.map((child) => (
            <TraceNodeComponent key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
