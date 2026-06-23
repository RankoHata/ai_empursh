import React, { useRef, useEffect } from 'react';

const PAGES = [
  { key: 'notes', icon: '📝', label: '笔记' },
  { key: 'chat', icon: '💬', label: '聊天' },
  { key: 'secret', icon: '🔒', label: '秘密' },
];

export default function BottomNavBar({ activePage, onPageChange, collapsed, onToggleCollapse, isSpeaking }) {
  const expandTimerRef = useRef(null);

  // Hover at bottom edge expands collapsed nav (macOS Dock style)
  const handleMouseEnterZone = () => {
    if (collapsed) {
      expandTimerRef.current = setTimeout(() => onToggleCollapse(), 150);
    }
  };

  const handleMouseLeaveZone = () => {
    if (expandTimerRef.current) {
      clearTimeout(expandTimerRef.current);
      expandTimerRef.current = null;
    }
  };

  // Cleanup timer
  useEffect(() => {
    return () => {
      if (expandTimerRef.current) clearTimeout(expandTimerRef.current);
    };
  }, []);

  return (
    <div className="bottom-nav-wrapper">
      {/* Hover detection zone (only when collapsed) */}
      {collapsed && (
        <div
          className="bottom-nav-hover-zone"
          onMouseEnter={handleMouseEnterZone}
          onMouseLeave={handleMouseLeaveZone}
        />
      )}

      {/* Nav content */}
      <div className={`bottom-nav ${collapsed ? 'bottom-nav-collapsed' : ''}`}>
        <div className="bottom-nav-items">
          {PAGES.map((page) => (
            <button
              key={page.key}
              className={`bottom-nav-item ${activePage === page.key ? 'active' : ''}`}
              onClick={() => onPageChange(page.key)}
              title={page.label}
            >
              <span className="bottom-nav-icon">
                {page.icon}
                {/* Speaking indicator: small floating note on chat icon */}
                {page.key === 'chat' && isSpeaking && (
                  <span className="bottom-nav-speaking-badge">♪</span>
                )}
              </span>
              <span className="bottom-nav-label">{page.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Collapse trigger line (always visible) */}
      <div
        className="bottom-nav-collapse-line"
        onClick={onToggleCollapse}
        title={collapsed ? '展开导航栏' : '折叠导航栏'}
      />
    </div>
  );
}
