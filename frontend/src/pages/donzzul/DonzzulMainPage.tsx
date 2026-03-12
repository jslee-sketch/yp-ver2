export default function DonzzulMainPage() {
    return (
        <div style={{
            maxWidth: '600px', margin: '0 auto', padding: '40px 20px',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: '64px', marginBottom: '16px' }}>💚</div>
            <h1 style={{ color: '#f472b6', marginBottom: '8px' }}>돈쭐</h1>
            <p style={{ color: '#888', fontSize: '15px', lineHeight: '1.6', marginBottom: '24px' }}>
                착한 가게를 응원하는 상품권 시스템<br/>
                따뜻한 소비로 세상을 바꿔요!
            </p>
            <div style={{
                padding: '16px', borderRadius: '12px',
                background: '#f472b610', border: '1px solid #f472b630',
                color: '#f472b6', fontSize: '14px',
                marginBottom: '24px',
            }}>
                곧 오픈합니다! 기대해주세요!
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
                <a href="/donzzul/hero/recommend" style={{
                    flex: 1, padding: '14px', borderRadius: '12px',
                    background: '#f472b620', border: '1px solid #f472b6',
                    color: '#f472b6', textAlign: 'center', textDecoration: 'none',
                    fontWeight: 'bold',
                }}>가게 추천하기</a>
                <a href="/donzzul/hero/my-stores" style={{
                    flex: 1, padding: '14px', borderRadius: '12px',
                    background: '#1a1a2e', border: '1px solid #2a2a4a',
                    color: '#888', textAlign: 'center', textDecoration: 'none',
                }}>내가 추천한 가게</a>
            </div>
        </div>
    )
}
