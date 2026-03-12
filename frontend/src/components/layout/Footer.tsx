import { useNavigate } from 'react-router-dom';

export default function Footer() {
  const navigate = useNavigate();

  return (
    <footer style={{
      padding: '24px 16px 100px',
      borderTop: '1px solid var(--border-subtle)',
      background: 'var(--bg-primary)',
    }}>
      {/* 통신판매중개 면책 */}
      <div style={{
        padding: '12px 14px',
        background: 'rgba(255,165,0,0.08)',
        border: '1px solid rgba(255,165,0,0.2)',
        borderRadius: 10,
        marginBottom: 16,
        fontSize: 11,
        color: '#b0b0b0',
        lineHeight: 1.6,
      }}>
        역핑은 통신판매중개자로서 거래 당사자가 아니며, 판매자가 등록한 상품 정보 및 거래에 대한 책임은 각 판매자에게 있습니다.
      </div>

      {/* 사업자 정보 */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8, marginBottom: 12 }}>
        <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--text-secondary)' }}>(주)텔러스테크</div>
        <div>대표: 대표자명</div>
        <div>사업자등록번호: 000-00-00000</div>
        <div>통신판매업 신고번호: 제0000-서울강남-00000호</div>
        <div>주소: 서울특별시</div>
        <div>이메일: support@yeokping.com</div>
      </div>

      {/* 링크 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <button
          onClick={() => navigate('/terms')}
          style={{ fontSize: 11, color: 'var(--text-secondary)', cursor: 'pointer', background: 'none', border: 'none', padding: 0, textDecoration: 'underline' }}
        >이용약관</button>
        <button
          onClick={() => navigate('/privacy')}
          style={{ fontSize: 11, color: 'var(--text-secondary)', cursor: 'pointer', background: 'none', border: 'none', padding: 0, textDecoration: 'underline' }}
        >개인정보처리방침</button>
      </div>

      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
        &copy; 2026 (주)텔러스테크. All rights reserved.
      </div>
    </footer>
  );
}
