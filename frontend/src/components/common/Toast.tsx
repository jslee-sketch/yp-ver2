export function showToast(
  message: string,
  type: 'success' | 'error' | 'info' = 'info',
) {
  const bgMap = {
    error:   'rgba(255,68,68,0.9)',
    success: 'rgba(0,255,136,0.9)',
    info:    'rgba(0,229,255,0.9)',
  };
  const colorMap = {
    error:   '#fff',
    success: '#0a0e1a',
    info:    '#0a0e1a',
  };

  const el = document.createElement('div');
  el.textContent = message;
  el.style.cssText = [
    'position:fixed',
    'bottom:100px',
    'left:50%',
    'transform:translateX(-50%)',
    'padding:12px 24px',
    'border-radius:12px',
    'z-index:9999',
    'font-size:13px',
    'font-weight:600',
    'white-space:nowrap',
    'pointer-events:none',
    'box-shadow:0 4px 20px rgba(0,0,0,0.3)',
    `background:${bgMap[type]}`,
    `color:${colorMap[type]}`,
  ].join(';');

  document.body.appendChild(el);

  setTimeout(() => {
    el.style.transition = 'opacity 0.3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }, 3000);
}
