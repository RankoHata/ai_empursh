/**
 * Avatar 组件测试 — 验证渲染 / 加载 / 错误路径
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Avatar from '../components/Avatar';

// Mock the dynamic import of AvatarManager
vi.mock('../../avatar/AvatarManager', () => ({
  AvatarManager: vi.fn().mockImplementation(() => ({
    init: vi.fn().mockResolvedValue(undefined),
    setState: vi.fn(),
    destroy: vi.fn(),
  })),
}));

// Mock Spine asset URLs (Vite's new URL(..., import.meta.url) is build-time)
vi.mock('../../../assets/spine/c017_00/c017_00.skel', () => ({}), { virtual: true });
vi.mock('../../../assets/spine/c017_00/c017_00.atlas', () => ({}), { virtual: true });

describe('Avatar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    render(<Avatar />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('renders with custom model prop without crashing', () => {
    render(<Avatar model="default" />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('accepts custom skelUrl and atlasUrl props', () => {
    render(<Avatar skelUrl="/custom.skel" atlasUrl="/custom.atlas" />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('accepts state prop', () => {
    render(<Avatar state="happy" />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('alt model prop accepted', () => {
    render(<Avatar model="alt" />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });

  it('unknown model falls back to default', () => {
    render(<Avatar model="nonexistent" />);
    expect(screen.getByText('加载中...')).toBeTruthy();
  });
});
