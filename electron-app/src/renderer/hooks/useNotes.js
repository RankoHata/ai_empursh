import { useState, useCallback } from 'react';

/**
 * useNotes — 笔记 + 秘密笔记 + Markdown 预览状态管理
 *
 * @param {Function} send — WebSocket send 函数
 */
export default function useNotes(send) {
  const [notes, setNotes] = useState([]);
  const [saveModal, setSaveModal] = useState(null);
  const [saveTags, setSaveTags] = useState('');
  const [newNoteModal, setNewNoteModal] = useState(null);
  const [secretNotes, setSecretNotes] = useState([]);
  const [secretNotification, setSecretNotification] = useState(null);
  const [markdownPreview, setMarkdownPreview] = useState(null);

  // ── 公开笔记 ──

  const handleGetNotes = useCallback(() => send('get_notes', {}), [send]);
  const handleSearchNotes = useCallback((q, t) => send('search_notes', { query: q, tags: t }), [send]);
  const handleDeleteNote = useCallback((id) => send('delete_note', { note_id: id }), [send]);
  const handleExportNotes = useCallback((ids) => send('export_notes', { note_ids: ids }), [send]);

  const handleSaveNote = useCallback((content) => {
    setSaveModal({ content });
    setSaveTags('');
  }, []);

  const handleConfirmSave = useCallback(() => {
    if (!saveModal) return;
    send('add_note', {
      content: saveModal.content,
      tags: saveTags.split(',').map(t => t.trim()).filter(Boolean),
    });
    setSaveModal(null);
    setSaveTags('');
  }, [saveModal, saveTags, send]);

  // ── 秘密笔记 ──

  const handleGetSecretNotes = useCallback(() => send('secret_get_notes', {}), [send]);
  const handleSearchSecretNotes = useCallback((q, t) => send('secret_search_notes', { query: q, tags: t }), [send]);
  const handleDeleteSecretNote = useCallback((id) => send('secret_delete_note', { note_id: id }), [send]);

  // ── 新建笔记弹窗（公开/秘密共用） ──

  const handleOpenNewNote = useCallback((secretMode = false) => {
    setNewNoteModal({ secretMode });
  }, []);

  const handleAddNoteFromModal = useCallback((content, tags, title) => {
    if (newNoteModal?.secretMode) {
      send('secret_add_note', { content, tags, title });
    } else {
      send('add_note', { content, tags, title });
    }
    setNewNoteModal(null);
    if (newNoteModal?.secretMode) {
      send('secret_get_notes', {});
    } else {
      send('get_notes', {});
    }
  }, [send, newNoteModal]);

  // ── Markdown 预览 ──

  const handleSaveMarkdown = useCallback((content, filename) => {
    send('save_file', { content, filename });
    setMarkdownPreview(null);
  }, [send]);

  const handleCancelPreview = useCallback(() => setMarkdownPreview(null), []);

  // ── WS 消息处理（由 App.jsx handleMessage 分发调用） ──

  const onMessage = useCallback((type, payload) => {
    switch (type) {
      case 'notes_list':
        setNotes(payload.notes || []);
        return true;
      case 'note_saved':
        return true; // consumed, no state change needed (will re-fetch)
      case 'note_deleted':
        setNotes(prev => prev.filter(n => n.id !== payload.note_id));
        return true;
      case 'search_results':
        setNotes(payload.results || []);
        return true;
      case 'notes_exported':
        alert(`笔记已导出到: ${payload.path}`);
        return true;
      case 'secret_notes_list':
        setSecretNotes(payload.notes || []);
        return true;
      case 'secret_note_saved':
        send('secret_get_notes', {});
        return true;
      case 'secret_note_deleted':
        setSecretNotes(prev => prev.filter(n => n.id !== payload.note_id));
        return true;
      case 'secret_search_results':
        setSecretNotes(payload.results || []);
        if (payload.count > 0) {
          setSecretNotification({ count: payload.count, query: payload.query });
        } else {
          setSecretNotification(null);
        }
        return true;
      case 'markdown_preview':
        setMarkdownPreview({ content: payload.content, suggestedFilename: payload.suggested_filename });
        return true;
      case 'file_saved':
        alert(`已保存到: ${payload.path}`);
        return true;
      default:
        return false; // not handled
    }
  }, [send]);

  return {
    // state
    notes,
    saveModal,
    saveTags,
    newNoteModal,
    secretNotes,
    secretNotification,
    markdownPreview,
    // setters (for modal state)
    setSaveTags,
    setSaveModal,
    setNewNoteModal,
    setMarkdownPreview,
    // handlers
    handleGetNotes,
    handleSearchNotes,
    handleDeleteNote,
    handleExportNotes,
    handleSaveNote,
    handleConfirmSave,
    handleGetSecretNotes,
    handleSearchSecretNotes,
    handleDeleteSecretNote,
    handleOpenNewNote,
    handleAddNoteFromModal,
    handleSaveMarkdown,
    handleCancelPreview,
    // for App.jsx dispatcher
    onMessage,
  };
}
