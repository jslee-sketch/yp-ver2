export default function PaymentSuccess({ amount }: { amount: number }) {
    return (
        <div style={{
            textAlign: 'center', padding: '40px',
            animation: 'fadeInUp 0.6s ease-out',
        }}>
            {/* 체크마크 원형 애니메이션 */}
            <div style={{
                width: '80px', height: '80px', borderRadius: '50%',
                background: '#4ade80', margin: '0 auto 20px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: 'scaleIn 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
                boxShadow: '0 0 40px rgba(74, 222, 128, 0.4)',
            }}>
                <span style={{ fontSize: '36px', color: '#000' }}>✓</span>
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#4ade80' }}>
                결제 완료!
            </div>
            <div style={{
                fontSize: '28px', fontWeight: 'bold', color: '#fff',
                marginTop: '8px', fontFamily: 'monospace',
            }}>
                ₩{amount.toLocaleString()}
            </div>
        </div>
    )
}
