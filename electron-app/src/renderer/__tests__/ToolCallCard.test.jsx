import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ToolCallCard from '../components/ToolCallCard';

describe('ToolCallCard', () => {
  it('renders running state', () => {
    render(<ToolCallCard toolCall={{
      id: '1', name: 'search_notes', args: { query: 'test' }, state: 'running',
    }} />);
    expect(screen.getByText('search_notes')).toBeTruthy();
    expect(screen.getByText(/执行中/)).toBeTruthy();
  });

  it('renders completed state with duration', () => {
    render(<ToolCallCard toolCall={{
      id: '1', name: 'search_notes', args: {}, state: 'completed',
      result: { message: 'Found 3 notes' }, duration_ms: 1500,
    }} />);
    expect(screen.getByText(/完成/)).toBeTruthy();
    expect(screen.getByText(/1.5s/)).toBeTruthy();
  });

  it('renders error state', () => {
    render(<ToolCallCard toolCall={{
      id: '1', name: 'search_notes', args: {}, state: 'error',
      error: 'Tool execution failed',
    }} />);
    expect(screen.getByText('search_notes')).toBeTruthy();
    expect(screen.getByText(/Tool execution failed/)).toBeTruthy();
  });

  it('strips mcp__ prefix for display', () => {
    render(<ToolCallCard toolCall={{
      id: '1', name: 'mcp__echo_echo', args: {}, state: 'completed',
      result: { message: 'OK' },
    }} />);
    expect(screen.getByText('echo_echo')).toBeTruthy();
  });

  it('shows expand/collapse toggle', () => {
    render(<ToolCallCard toolCall={{
      id: '1', name: 'test_tool', args: {}, state: 'completed',
      result: { message: 'done' },
    }} />);
    // The expand toggle button exists
    expect(screen.getByTitle(/点击展开/)).toBeTruthy();
  });
});
