'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { getProjects, createProject, deleteProject, createRun, Project } from '@/lib/api';
import { useRouter } from 'next/navigation';

export default function ProjectsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projName, setProjName] = useState('');
  const [projDesc, setProjDesc] = useState('');
  const [projRepo, setProjRepo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const list = await getProjects();
      setProjects(list);
    } catch (err: any) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projName) return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await createProject(projName, projDesc, projRepo || undefined);
      setProjects((prev) => [created, ...prev]);
      setProjName('');
      setProjDesc('');
      setProjRepo('');
      setIsModalOpen(false);
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this project?')) return;
    setError(null);
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      setError(err.message || 'Failed to delete project');
    }
  };

  const handleOpenWorkspace = async (project: Project) => {
    // Check if we can create a run or redirect to execution
    setError(null);
    try {
      // By default, create a default run if opening workspace, or redirect to a run screen where they can start a run.
      // We will redirect to a page like `/runs/new?project=${project.id}` or just allow them to pick the run.
      // Since Part 4 outlines the Agent Execution screen is `app/runs/[runId]/page.tsx`, we can create a run with a simple task or redirect to the execution board.
      // Let's redirect to `/runs/new?project=${project.id}` where they can type their task and see live executions!
      // Wait, we can implement `app/runs/page.tsx` or let them launch it.
      // Let's make it so when they click "Open Workspace", we redirect to `/runs/new?project=${project.id}` to enter the prompt. Or we can just launch the workspace view.
      router.push(`/runs/workspace?project=${project.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to open workspace');
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 p-6 md:p-12 relative">
      {/* Glow effects */}
      <div className="absolute top-10 right-10 w-96 h-96 bg-violet-600/5 rounded-full filter blur-[100px] pointer-events-none"></div>
      <div className="absolute bottom-10 left-10 w-96 h-96 bg-emerald-600/5 rounded-full filter blur-[100px] pointer-events-none"></div>

      {/* Main Container */}
      <div className="max-w-6xl mx-auto space-y-8 relative z-10">
        
        {/* Navigation Bar */}
        <header className="flex flex-col sm:flex-row items-center justify-between border-b border-zinc-800 pb-6 gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-tr from-violet-600 to-indigo-500 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-semibold">Antigravity Console</h1>
              <p className="text-xs text-zinc-500">Welcome back, {user?.name || 'Developer'}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/memory')}
              className="bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white px-4 py-2 rounded-xl text-sm font-medium transition-colors"
            >
              Memory Debugger
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span>New Project</span>
            </button>
            <button
              onClick={logout}
              className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 px-4 py-2 rounded-xl text-sm font-medium transition-colors"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Global Errors */}
        {error && (
          <div className="bg-red-950/40 border border-red-900/60 rounded-xl p-4 text-sm text-red-400 flex gap-2">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Project Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-zinc-900/40 border border-zinc-800 rounded-2xl h-48 animate-pulse animate-shimmer"></div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center border border-dashed border-zinc-800 rounded-2xl p-16 text-center bg-zinc-900/10">
            <svg className="w-12 h-12 text-zinc-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <h3 className="text-lg font-semibold text-zinc-300">No projects found</h3>
            <p className="text-zinc-500 text-sm max-w-sm mt-1 mb-6">Create a project to connect your local codebase and run agent workflows.</p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="bg-violet-600 hover:bg-violet-500 text-white px-5 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              Create your first project
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => handleOpenWorkspace(project)}
                className="group bg-zinc-900/40 hover:bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-6 shadow-lg transition-all duration-300 cursor-pointer flex flex-col justify-between h-48 relative overflow-hidden"
              >
                {/* Visual Glow on Hover */}
                <div className="absolute top-0 right-0 w-24 h-24 bg-violet-600/10 rounded-full filter blur-[30px] opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

                <div className="space-y-2 relative z-10">
                  <h3 className="font-semibold text-lg text-zinc-200 group-hover:text-white transition-colors">
                    {project.name}
                  </h3>
                  <p className="text-zinc-400 text-sm line-clamp-2">
                    {project.description || 'No description provided.'}
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-zinc-800/80 pt-4 mt-4 relative z-10">
                  <span className="text-xs font-mono text-zinc-600 truncate max-w-[150px]">
                    {project.repo_path ? `📁 ${project.repo_path.split('/').pop()}` : 'No repo connected'}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={(e) => handleDeleteProject(project.id, e)}
                      className="text-zinc-500 hover:text-red-400 p-1.5 rounded-lg hover:bg-zinc-800 transition-colors"
                      title="Delete Project"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                    <span className="text-violet-400 group-hover:text-violet-300 text-sm font-medium flex items-center gap-1">
                      <span>Open</span>
                      <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Creation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-zinc-100">Create New Project</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-zinc-500 hover:text-zinc-300 rounded-lg p-1 hover:bg-zinc-800"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Project Name</label>
                <input
                  type="text"
                  required
                  value={projName}
                  onChange={(e) => setProjName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-2.5 px-3.5 text-sm text-zinc-200 focus:outline-none focus:border-violet-600"
                  placeholder="e.g. Codebase Architect"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Description</label>
                <textarea
                  value={projDesc}
                  onChange={(e) => setProjDesc(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-2.5 px-3.5 text-sm text-zinc-200 focus:outline-none focus:border-violet-600 h-20 resize-none"
                  placeholder="What does this project do?"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Repository Absolute Path (Optional)</label>
                <input
                  type="text"
                  value={projRepo}
                  onChange={(e) => setProjRepo(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-2.5 px-3.5 text-sm text-zinc-200 focus:outline-none focus:border-violet-600"
                  placeholder="e.g. /Users/name/projects/my-app"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-violet-600 hover:bg-violet-500 text-white font-medium py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2 shadow-lg shadow-violet-500/10"
              >
                {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
                <span>Create Project</span>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
