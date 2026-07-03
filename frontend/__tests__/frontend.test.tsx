import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/lib/auth';
import { useWebSocket } from '@/hooks/useWebSocket';
import RunExecutionPage from '../app/runs/[runId]/page';
import { resumeRun } from '@/lib/api';
import { buildTraceTree } from '@/lib/utils';

// Mock navigation variables globally
const mockReplace = vi.fn();
const mockPush = vi.fn();

vi.mock('next/navigation', () => {
  return {
    useRouter: () => ({
      push: mockPush,
      replace: mockReplace,
      prefetch: vi.fn(),
    }),
    usePathname: () => '/projects',
    useSearchParams: () => ({
      get: (key: string) => (key === 'project' ? 'proj_test_id' : null),
    }),
    useParams: () => ({ runId: 'run_123' }),
  };
});

// Mock API calls
vi.mock('@/lib/api', () => {
  return {
    API_BASE_URL: 'http://localhost:8000',
    WS_BASE_URL: 'ws://localhost:8000',
    loginWithGoogle: vi.fn(async (idToken: string) => {
      if (idToken === 'mock_token_rishi') {
        return { access_token: 'header.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoicmlzaGlAZXhhbXBsZS5jb20iLCJuYW1lIjoiUmlzaGkifQ.signature' };
      }
      throw new Error('Invalid token');
    }),
    getProjects: vi.fn(async () => []),
    getRunDetails: vi.fn(async (runId: string) => ({
      status: 'interrupted',
      current_agent: 'developer',
      timeline: [{ agent: 'Supervisor', timestamp: new Date().toISOString(), details: 'Starting test run' }],
      trace: [
        { id: '1', agent: 'Supervisor', parent_trace_id: null, tool_called: null, status: 'SUCCESS', latency: 0.2 },
        { id: '2', agent: 'Developer', parent_trace_id: '1', tool_called: 'read_file', status: 'PENDING_APPROVAL', latency: 1.1 }
      ]
    })),
    resumeRun: vi.fn(async (runId: string, approved: boolean) => ({ status: 'resuming' })),
    getRunMetrics: vi.fn(async () => ({ total_steps: 5, avg_latency: 1.5, total_tool_calls: 3, failed_tool_calls: 0 })),
    getRunReflections: vi.fn(async () => [])
  };
});

// Mock Component for basic Auth Context verification
const TestComponent = () => {
  const { isAuthenticated, user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="auth-state">{isAuthenticated ? 'logged-in' : 'logged-out'}</span>
      <span data-testid="user-email">{user?.email || 'none'}</span>
      <button onClick={() => login('mock_token_rishi')}>Log In</button>
      <button onClick={logout}>Log Out</button>
    </div>
  );
};

// Helper to render protected routes
const ProtectedTestWrapper = () => {
  return (
    <AuthProvider>
      <div>Protected Content</div>
    </AuthProvider>
  );
};

describe('Next.js Frontend Workspace UI Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  // --- Test 1: Login Flow & Storage ---
  it('should authenticate user and save JWT to localStorage on successful login', async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-state')).toHaveTextContent('logged-out');

    // Click login button
    fireEvent.click(screen.getByText('Log In'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('logged-in');
    });

    expect(screen.getByTestId('user-email')).toHaveTextContent('rishi@example.com');
    expect(localStorage.getItem('agent_jwt')).toContain('header.eyJzdWI');
  });

  // --- Test 2: Protected Routes (Redirects) ---
  it('should redirect unauthenticated users to /login page', async () => {
    render(<ProtectedTestWrapper />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/login');
    });
  });

  // --- Test 3: Trace Rendering Hierarchy ---
  it('should correctly build hierarchical trace tree structure from flat spans', () => {
    const flatTraces = [
      { id: 'root', agent: 'Supervisor', parent_trace_id: null, tool_called: null, status: 'SUCCESS', latency: 0.1, timestamp: '' },
      { id: 'child-1', agent: 'Developer', parent_trace_id: 'root', tool_called: 'read_file', status: 'SUCCESS', latency: 0.5, timestamp: '' },
      { id: 'child-2', agent: 'Researcher', parent_trace_id: 'root', tool_called: null, status: 'SUCCESS', latency: 0.8, timestamp: '' },
      { id: 'grandchild', agent: 'Tool', parent_trace_id: 'child-1', tool_called: 'git_status', status: 'SUCCESS', latency: 0.2, timestamp: '' }
    ];

    const tree = buildTraceTree(flatTraces);

    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe('root');
    expect(tree[0].children).toHaveLength(2);
    
    // Check developer child
    const devChild = tree[0].children.find(c => c.id === 'child-1');
    expect(devChild).toBeDefined();
    expect(devChild?.children).toHaveLength(1);
    expect(devChild?.children[0].id).toBe('grandchild');
  });

  // --- Test 4: WebSocket Updates Mock ---
  it('should establish WebSocket connections and receive parsed events', async () => {
    const mockWebSocketInstance = {
      close: vi.fn(),
      onopen: vi.fn(),
      onmessage: vi.fn(),
      onerror: vi.fn(),
      onclose: vi.fn()
    };

    const MockWebSocket = vi.fn().mockImplementation(() => mockWebSocketInstance);
    vi.stubGlobal('WebSocket', MockWebSocket);

    // Seed Auth State in localStorage before rendering
    localStorage.setItem('agent_jwt', 'header.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoicmlzaGlAZXhhbXBsZS5jb20iLCJuYW1lIjoiUmlzaGkifQ.signature');

    const TestHookComponent = () => {
      const { connected, events } = useWebSocket('run_123');
      return (
        <div>
          <span data-testid="ws-conn">{connected ? 'connected' : 'disconnected'}</span>
          <span data-testid="ws-events">{events.length}</span>
        </div>
      );
    };

    render(
      <AuthProvider>
        <TestHookComponent />
      </AuthProvider>
    );

    // Simulate socket open
    mockWebSocketInstance.onopen();

    await waitFor(() => {
      expect(screen.getByTestId('ws-conn')).toHaveTextContent('connected');
    });

    // Simulate incoming step message
    mockWebSocketInstance.onmessage({
      data: JSON.stringify({
        type: 'agent_step',
        agent: 'developer',
        content: 'Editing codebase auth module.'
      })
    });

    await waitFor(() => {
      expect(screen.getByTestId('ws-events')).toHaveTextContent('1');
    });
  });

  // --- Test 5: Human Approval Resume Calls ---
  it('should trigger resume api call when Human approves pending actions', async () => {
    // Set authenticated token
    localStorage.setItem('agent_jwt', 'header.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoicmlzaGlAZXhhbXBsZS5jb20iLCJuYW1lIjoiUmlzaGkifQ.signature');

    render(
      <AuthProvider>
        <RunExecutionPage />
      </AuthProvider>
    );

    // Wait for approval dialog to render
    await waitFor(() => {
      expect(screen.getByText('Dangerous Action Verification Required')).toBeInTheDocument();
    });

    // Click Approve button
    fireEvent.click(screen.getByText('Approve & Continue'));

    expect(resumeRun).toHaveBeenCalledWith('run_123', true, undefined);
  });
});
