import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  /** "70vh" | "80vh" | number (px) — default "70vh" */
  height?: string | number;
  children: React.ReactNode;
}

export const BottomSheet: React.FC<BottomSheetProps> = ({
  isOpen,
  onClose,
  title,
  height = '70vh',
  children,
}) => {
  const sheetRef = useRef<HTMLDivElement>(null);

  // body scroll lock
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  // ESC 닫기
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const heightValue = typeof height === 'number' ? `${height}px` : height;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* 배경 딤 */}
          <motion.div
            key="dim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 300,
            }}
          />

          {/* 시트 */}
          <motion.div
            key="sheet"
            ref={sheetRef}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={{ top: 0, bottom: 0.2 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 80 || info.velocity.y > 600) onClose();
            }}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            style={{
              position: 'fixed',
              bottom: 0,
              left: '50%',
              transform: 'translateX(-50%)',
              width: '100%',
              maxWidth: 428,
              height: heightValue,
              background: 'var(--bg-secondary)',
              borderRadius: '20px 20px 0 0',
              zIndex: 301,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              touchAction: 'pan-y',
            }}
          >
            {/* 드래그 핸들 */}
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              padding: '12px 0 8px',
              flexShrink: 0,
              cursor: 'grab',
            }}>
              <div style={{
                width: 36,
                height: 4,
                borderRadius: 2,
                background: 'var(--bg-elevated)',
              }} />
            </div>

            {/* 헤더 */}
            {title && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 20px 12px',
                flexShrink: 0,
                borderBottom: '1px solid var(--border-subtle)',
              }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {title}
                </span>
                <button
                  onClick={onClose}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-muted)',
                    fontSize: 14,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  aria-label="닫기"
                >
                  ✕
                </button>
              </div>
            )}

            {/* 콘텐츠 스크롤 영역 */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              overscrollBehavior: 'contain',
            }}>
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
