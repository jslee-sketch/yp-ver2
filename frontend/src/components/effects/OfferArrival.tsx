export default function OfferArrival({ active, sellerName, price }: {
    active: boolean, sellerName: string, price: number
}) {
    if (!active) return null

    return (
        <div style={{
            animation: 'offerBounceIn 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
            position: 'relative',
        }}>
            {/* 탁구공 */}
            <div style={{
                position: 'absolute', top: '-10px', left: '-10px',
                width: '24px', height: '24px', borderRadius: '50%',
                background: 'radial-gradient(circle at 30% 30%, #fff, #ddd)',
                boxShadow: '0 0 12px rgba(74, 222, 128, 0.5)',
                animation: 'pingpongSpin 0.6s ease-out',
                zIndex: 1,
            }} />

            {/* 오퍼 카드 */}
            <div style={{
                background: 'rgba(26, 26, 46, 0.9)',
                backdropFilter: 'blur(8px)',
                border: '1px solid #4ade80',
                borderRadius: '12px', padding: '16px',
                boxShadow: '0 0 20px rgba(74, 222, 128, 0.2)',
            }}>
                <div style={{ color: '#4ade80', fontSize: '13px' }}>🏓 새 오퍼 도착!</div>
                <div style={{ color: '#e0e0e0', fontSize: '18px', fontWeight: 'bold', marginTop: '4px' }}>
                    ₩{price.toLocaleString()}
                </div>
                <div style={{ color: '#888', fontSize: '12px' }}>{sellerName}</div>
            </div>
        </div>
    )
}
