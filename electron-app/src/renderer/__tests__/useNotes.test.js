import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useNotes from '../hooks/useNotes';

describe('useNotes', () => {
  let send;

  beforeEach(() => {
    send = vi.fn();
  });

  it('starts with empty state', () => {
    const { result } = renderHook(() => useNotes(send));
    expect(result.current.notes).toEqual([]);
    expect(result.current.secretNotes).toEqual([]);
    expect(result.current.saveModal).toBeNull();
    expect(result.current.markdownPreview).toBeNull();
  });

  it('handleSaveNote opens save modal', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => { result.current.handleSaveNote('some markdown content'); });
    expect(result.current.saveModal).toEqual({ content: 'some markdown content' });
  });

  it('handleConfirmSave sends add_note', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => { result.current.handleSaveNote('test content'); });
    act(() => { result.current.setSaveTags('tag1, tag2'); });
    act(() => { result.current.handleConfirmSave(); });
    expect(send).toHaveBeenCalledWith('add_note', expect.objectContaining({
      content: 'test content',
      tags: ['tag1', 'tag2'],
    }));
  });

  it('onMessage notes_list sets notes', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => {
      result.current.onMessage('notes_list', { notes: [{ id: 1, content: 'note1' }] });
    });
    expect(result.current.notes).toHaveLength(1);
  });

  it('onMessage note_deleted filters note', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => { result.current.onMessage('notes_list', { notes: [{ id: 1 }, { id: 2 }] }); });
    act(() => { result.current.onMessage('note_deleted', { note_id: 1 }); });
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.notes[0].id).toBe(2);
  });

  it('onMessage secret_search_results sets notification', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => {
      result.current.onMessage('secret_search_results', {
        results: [{ id: 1 }], count: 1, query: 'test',
      });
    });
    expect(result.current.secretNotification).toEqual({ count: 1, query: 'test' });
  });

  it('handleOpenNewNote opens modal', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => { result.current.handleOpenNewNote(true); });
    expect(result.current.newNoteModal).toEqual({ secretMode: true });
  });

  it('handleAddNoteFromModal sends to correct endpoint', () => {
    const { result } = renderHook(() => useNotes(send));
    act(() => { result.current.handleOpenNewNote(true); });
    act(() => {
      result.current.handleAddNoteFromModal('secret content', ['private'], 'title');
    });
    expect(send).toHaveBeenCalledWith('secret_add_note', expect.objectContaining({
      content: 'secret content',
    }));
  });
});
