import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''

export default function DonzzulMainPage() {
    const [deals, setDeals] = useState<any[]>([])

    useEffect(() => {
        fetch(`${API}/donzzul/deals?status=OPEN`).then(r => r.json()).then(data => {
            setDeals(Array.isArray(data) ? data : [])
        })
    }, [])

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

            <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
                <a href="/donzzul/hero/recommend" style={{
                    flex: 1, padding: '14px', borderRadius: '12px',
                    background: '#f472b620', border: '1px solid #f472b6',
                    color: '#f472b6', textAlign: 'center', textDecoration: 'none',
                    fontWeight: 'bold',
                }}>가게 추천하기</a>
                <Link to="/donzzul/vouchers" style={{
                    flex: 1, padding: '14px', borderRadius: '12px',
                    background: '#4ade8020', border: '1px solid #4ade80',
                    color: '#4ade80', textAlign: 'center', textDecoration: 'none',
                    fontWeight: 'bold',
                }}>🎫 내 상품권함</Link>
                <a href="/donzzul/hero/my-stores" style={{
                    flex: 1, padding: '14px', borderRadius: '12px',
                    background: '#1a1a2e', border: '1px solid #2a2a4a',
                    color: '#888', textAlign: 'center', textDecoration: 'none',
                }}>내가 추천한 가게</a>
            </div>

            {/* OPEN 딜 목록 */}
            {deals.length > 0 && (
                <div style={{ textAlign: 'left' }}>
                    <div style={{ color: '#888', fontSize: '13px', marginBottom: '8px' }}>
                        💚 응원 가능한 가게 ({deals.length}곳)
                    </div>
                    {deals.map(deal => (
                        <Link to={`/donzzul/deals/${deal.id}`} key={deal.id} style={{
                            display: 'block', background: '#1a1a2e', borderRadius: '12px',
                            padding: '16px', marginBottom: '8px', textDecoration: 'none',
                        }}>
                            <div style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{deal.title}</div>
                            <div style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                                {deal.voucher_count || 0}명 응원 | {(deal.current_amount || 0).toLocaleString()}원
                            </div>
                        </Link>
                    ))}
                </div>
            )}

            {deals.length === 0 && (
                <div style={{
                    padding: '16px', borderRadius: '12px',
                    background: '#f472b610', border: '1px solid #f472b630',
                    color: '#f472b6', fontSize: '14px',
                }}>
                    아직 응원 가능한 가게가 없어요. 가게를 추천해주세요!
                </div>
            )}
        </div>
    )
}
