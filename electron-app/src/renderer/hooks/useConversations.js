import { useState, useCallback } from 'react';

/**
 * useConversations — 对话列表 + 加载 + CRUD
 *
 * @param {Function} send      — WebSocket send 函数
 * @param {Function} clearMessages — 清空聊天消息（由 useChat 提供）
 */
export default function useConversations(send, clearMessages) {
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);

  const handleNewConv = useCallback(() => {
    clearMessages();
    send('create_conversation', {});
  }, [send, clearMessages]);

  const handleSelectConv = useCallback((convId) => {
    clearMessages();
    setActiveConvId(convId);
    send('load_conversation', { conversation_id: convId });
  }, [send, clearMessages]);

  const handleDeleteConv = useCallback((convId) => {
    send('delete_conversation', { conversation_id: convId });
  }, [send]);

  const handleRenameConv = useCallback((convId, title) => {
    send('rename_conversation', { conversation_id: convId, title });
  }, [send]);

  const onMessage = useCallback((type, payload) => {
    switch (type) {
      case 'conversation_created':
        setActiveConvId(payload.conversation?.id || null);
        setConversations(prev => {
          if (payload.conversation && !prev.find(c => c.id === payload.conversation.id)) {
            return [...prev, payload.conversation];
          }
          return prev;
        });
        return true;
      case 'conversations_list':
        setConversations(payload.conversations || []);
        return true;
      case 'conversation_deleted':
        setConversations(prev => prev.filter(c => c.id !== payload.conversation_id));
        if (activeConvId === payload.conversation_id) {
          setActiveConvId(null);
          clearMessages();
        }
        return true;
      case 'turn_deleted':
        return true; // handled by useChat
      case 'conversation_renamed':
        if (payload.conversation) {
          setConversations(prev => prev.map(c =>
            c.id === payload.conversation.id ? payload.conversation : c
          ));
        }
        return true;
      case 'conversation_loaded':
        send('get_turns', { conversation_id: payload.conversation_id });
        return true;
      default:
        return false;
    }
  }, [send, clearMessages, activeConvId]);

  return {
    conversations,
    activeConvId,
    handleNewConv,
    handleSelectConv,
    handleDeleteConv,
    handleRenameConv,
    onMessage,
  };
}
