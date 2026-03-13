import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''

export default function DonzzulDealPage() {
    const { id } = useParams()
    const [data, setData] = useState<any>(null)
    const [selectedAmount, setSelectedAmount] = useState(10000)
    const [cheerMessage, setCheerMessage] = useState('')
    const [purchasing, setPurchasing] = useState(false)
    const [purchaseResult, setPurchaseResult] = useState<any>(null)

    useEffect(() => {
        fetch(`${API}/donzzul/deals/${id}`).then(r => r.json()).then(setData)
    }, [id])

    if (!data) return <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>로딩 중...</div>

    const { deal, store, cheer_messages } = data

    const purchase = async () => {
        setPurchasing(true)
        const token = localStorage.getItem('token')
        const user = JSON.parse(localStorage.getItem('user') || '{}')

        const r = await fetch(`${API}/donzzul/vouchers/purchase`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                deal_id: deal.id,
                buyer_id: user.id,
                amount: selectedAmount,
                cheer_message: cheerMessage,
            }),
        })

        if (r.ok) {
            const result = await r.json()
            setPurchaseResult(result)
        } else {
            const err = await r.json()
            alert(err.detail || '구매 실패')
        }
        setPurchasing(false)
    }

    // 구매 완료 화면
    if (purchaseResult) {
        return (
            <div style={{ maxWidth: '500px', margin: '0 auto', padding: '40px 20px', textAlign: 'center' }}>
                <div style={{ fontSize: '64px', marginBottom: '16px' }}>🎉</div>
                <h1 style={{ color: '#f472b6', marginBottom: '8px' }}>상품권 발급 완료!</h1>
                <p style={{ color: '#888', marginBottom: '24px' }}>
                    {purchaseResult.store_name}을(를) 응원해주셔서 감사해요!
                </p>

                <div style={{
                    background: '#1a1a2e', borderRadius: '16px', padding: '24px',
                    marginBottom: '16px', textAlign: 'left',
                }}>
                    <div style={{ color: '#888', fontSize: '12px', marginBottom: '4px' }}>상품권 코드</div>
                    <div style={{ color: '#4ade80', fontSize: '18px', fontWeight: 'bold', marginBottom: '12px' }}>
                        {purchaseResult.code}
                    </div>
                    <div style={{ color: '#888', fontSize: '12px', marginBottom: '4px' }}>비밀번호 (이 화면에서만 확인 가능!)</div>
                    <div style={{ color: '#f59e0b', fontSize: '24px', fontWeight: 'bold', letterSpacing: '8px', marginBottom: '12px' }}>
                        {purchaseResult.pin}
                    </div>
                    <div style={{ color: '#ef4444', fontSize: '11px' }}>
                        ⚠️ 비밀번호는 다시 확인할 수 없습니다. 꼭 기억해주세요!
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                    <a href="/donzzul/vouchers" style={{
                        flex: 1, padding: '14px', borderRadius: '12px',
                        background: '#f472b6', color: '#fff', textDecoration: 'none',
                        textAlign: 'center', fontWeight: 'bold',
                    }}>내 상품권함 →</a>
                    <a href="/donzzul" style={{
                        flex: 1, padding: '14px', borderRadius: '12px',
                        background: '#2a2a4a', color: '#888', textDecoration: 'none',
                        textAlign: 'center',
                    }}>돈쭐 메인</a>
                </div>
            </div>
        )
    }

    return (
        <div style={{ maxWidth: '500px', margin: '0 auto', padding: '20px' }}>
            {/* 유튜브 임베드 */}
            {store?.youtube_url && (
                <div style={{ marginBottom: '16px', borderRadius: '12px', overflow: 'hidden' }}>
                    <iframe
                        width="100%" height="280"
                        src={store.youtube_url.replace('watch?v=', 'embed/')}
                        frameBorder="0" allowFullScreen
                        style={{ borderRadius: '12px' }}
                    />
                </div>
            )}

            {/* 가게 정보 */}
            <div style={{ marginBottom: '16px' }}>
                <h1 style={{ color: '#e0e0e0', marginBottom: '4px' }}>{deal.title}</h1>
                <div style={{ color: '#888', fontSize: '13px' }}>
                    📍 {store?.store_address} | {store?.store_category}
                </div>
            </div>

            {/* 달성률 */}
            <div style={{
                background: '#1a1a2e', borderRadius: '12px', padding: '16px',
                marginBottom: '16px',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ color: '#888', fontSize: '13px' }}>달성률</span>
                    <span style={{ color: '#f472b6', fontWeight: 'bold' }}>{deal.progress}%</span>
                </div>
                <div style={{
                    height: '8px', background: '#2a2a4a', borderRadius: '4px', overflow: 'hidden',
                }}>
                    <div style={{
                        height: '100%', width: `${Math.min(deal.progress, 100)}%`,
                        background: 'linear-gradient(90deg, #f472b6, #4ade80)',
                        borderRadius: '4px', transition: 'width 0.5s',
                    }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '12px', color: '#888' }}>
                    <span>{deal.current_amount?.toLocaleString()}원 ({deal.voucher_count}명)</span>
                    <span>목표 {deal.target_amount?.toLocaleString()}원</span>
                </div>
            </div>

            {/* 사연 */}
            <div style={{
                background: '#1a1a2e', borderRadius: '12px', padding: '16px',
                marginBottom: '16px', lineHeight: '1.7',
            }}>
                <div style={{ color: '#f472b6', fontSize: '13px', fontWeight: 'bold', marginBottom: '8px' }}>
                    💬 이 가게의 사연
                </div>
                <div style={{ color: '#e0e0e0', fontSize: '14px' }}>
                    {store?.story_text}
                </div>
            </div>

            {/* 상품권 구매 */}
            {deal.status === 'OPEN' && (
                <div style={{
                    background: '#1a1a2e', borderRadius: '12px', padding: '16px',
                    marginBottom: '16px',
                }}>
                    <div style={{ color: '#f472b6', fontSize: '13px', fontWeight: 'bold', marginBottom: '12px' }}>
                        💚 상품권 구매
                    </div>

                    <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                        {[10000, 20000, 50000].map(amt => (
                            <button key={amt} onClick={() => setSelectedAmount(amt)}
                                style={{
                                    flex: 1, padding: '14px', borderRadius: '10px',
                                    background: selectedAmount === amt ? '#f472b620' : '#0f0f1a',
                                    border: `2px solid ${selectedAmount === amt ? '#f472b6' : '#2a2a4a'}`,
                                    color: selectedAmount === amt ? '#f472b6' : '#888',
                                    cursor: 'pointer', fontSize: '15px', fontWeight: 'bold',
                                }}>
                                {(amt/10000)}만원
                            </button>
                        ))}
                    </div>

                    <input value={cheerMessage} onChange={e => setCheerMessage(e.target.value)}
                        placeholder="응원 한마디 (선택)"
                        maxLength={200}
                        style={{
                            width: '100%', padding: '12px', borderRadius: '8px',
                            background: '#0f0f1a', color: '#e0e0e0',
                            border: '1px solid #2a2a4a', fontSize: '14px',
                            marginBottom: '12px', boxSizing: 'border-box',
                        }} />

                    <button onClick={purchase} disabled={purchasing}
                        style={{
                            width: '100%', padding: '16px', borderRadius: '12px',
                            background: purchasing ? '#666' : '#f472b6', color: '#fff',
                            border: 'none', cursor: 'pointer', fontSize: '16px', fontWeight: 'bold',
                        }}>
                        {purchasing ? '결제 중...' : `💚 ${selectedAmount.toLocaleString()}원 응원하기`}
                    </button>

                    <div style={{ color: '#666', fontSize: '11px', textAlign: 'center', marginTop: '8px' }}>
                        역핑 수수료 0원 | 유효기간 90일 | 만료 시 가게에 자동 기부
                    </div>
                </div>
            )}

            {/* 응원 메시지 */}
            {cheer_messages.length > 0 && (
                <div>
                    <div style={{ color: '#888', fontSize: '13px', marginBottom: '8px' }}>
                        💬 응원 메시지 ({cheer_messages.length}건)
                    </div>
                    {cheer_messages.map((m: any, i: number) => (
                        <div key={i} style={{
                            background: '#1a1a2e', borderRadius: '8px', padding: '10px',
                            marginBottom: '4px', display: 'flex', justifyContent: 'space-between',
                        }}>
                            <span style={{ color: '#e0e0e0', fontSize: '13px' }}>"{m.message}"</span>
                            <span style={{ color: '#888', fontSize: '11px', whiteSpace: 'nowrap' }}>
                                {(m.amount/10000)}만원
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
