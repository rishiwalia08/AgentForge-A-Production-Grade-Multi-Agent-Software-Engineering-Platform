import '@testing-library/jest-dom';
import * as matchers from '@testing-library/jest-dom/matchers';
import { expect, vi } from 'vitest';

// Extend Vitest's expect with Testing Library's matchers
expect.extend(matchers);

// Mock Next.js navigation router hooks
vi.mock('next/navigation', () => {
  const useRouter = vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }));
  const usePathname = vi.fn(() => '/');
  const useSearchParams = vi.fn(() => ({
    get: vi.fn((key: string) => (key === 'project' ? 'proj_test_id' : null)),
  }));
  return {
    useRouter,
    usePathname,
    useSearchParams,
  };
});

// Mock browser APIs
global.window.atob = (str: string) => Buffer.from(str, 'base64').toString('binary');
global.window.btoa = (str: string) => Buffer.from(str, 'binary').toString('base64');
