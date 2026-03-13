import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''

const STATUS_STYLE: Record<string, { label: string, color: string }> = {
    ACTIVE: { label: '사용 가능', color: '#4ade80' },
    USED: { label: '사용 완료', color: '#888' },
    EXPIRED: { label: '만료', color: '#f59e0b' },
    DONATED: { label: '가게에 기부됨', color: '#f472b6' },
    REFUNDED: { label: '환불됨', color: '#60a5fa' },
}

export default function DonzzulVouchersPage() {
    const [vouchers, setVouchers] = useState<any[]>([])

    useEffect(() => {
        const token = localStorage.getItem('token')
        const user = JSON.parse(localStorage.getItem('user') || '{}')
        fetch(`${API}/donzzul/vouchers/my?buyer_id=${user.id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()).then(data => setVouchers(Array.isArray(data) ? data : []))
    }, [])

    return (
        <div style={{ maxWidth: '500px', margin: '0 auto', padding: '20px' }}>
            <h1 style={{ color: '#f472b6', marginBottom: '16px' }}>🎫 내 상품권함</h1>

            {vouchers.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                    상품권이 없어요.<br/>
                    <a href="/donzzul" style={{ color: '#f472b6' }}>돈쭐 딜에서 응원해보세요! 💚</a>
                </div>
            )}

            {vouchers.map(v => {
                const status = STATUS_STYLE[v.status] || { label: v.status, color: '#888' }
                const isActive = v.status === 'ACTIVE'

                return (
                    <div key={v.id} style={{
                        background: isActive
                            ? 'linear-gradient(135deg, #1a1a2e 0%, #2a1a3e 50%, #1a2a3e 100%)'
                            : '#1a1a2e',
                        borderRadius: '16px', padding: '20px', marginBottom: '12px',
                        border: isActive ? '1px solid #f472b650' : '1px solid #2a2a4a',
                        position: 'relative', overflow: 'hidden',
                    }}>
                        {/* 홀로그램 효과 (ACTIVE만) */}
                        {isActive && (
                            <div style={{
                                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                                background: 'linear-gradient(135deg, transparent 30%, rgba(244,114,182,0.05) 50%, transparent 70%)',
                                pointerEvents: 'none',
                            }} />
                        )}

                        {/* 상단 */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                            <div>
                                <div style={{ color: '#e0e0e0', fontWeight: 'bold', fontSize: '15px' }}>
                                    {v.store_name}
                                </div>
                                <div style={{ color: '#888', fontSize: '11px' }}>{v.store_address}</div>
                            </div>
                            <span style={{
                                padding: '2px 10px', borderRadius: '12px', height: 'fit-content',
                                background: `${status.color}20`, color: status.color,
                                fontSize: '11px', fontWeight: 'bold',
                            }}>{status.label}</span>
                        </div>

                        {/* 금액 */}
                        <div style={{
                            fontSize: '28px', fontWeight: 'bold', marginBottom: '12px',
                            color: isActive ? '#f472b6' : '#666',
                        }}>
                            ₩{v.amount.toLocaleString()}
                        </div>

                        {/* 코드 */}
                        <div style={{ color: '#888', fontSize: '12px', marginBottom: '4px' }}>
                            {v.code}
                        </div>

                        {/* 유효기간 */}
                        <div style={{
                            color: isActive && v.days_left <= 14 ? '#f59e0b' : '#666',
                            fontSize: '12px', marginBottom: '12px',
                        }}>
                            {isActive
                                ? `유효기간: ${v.expires_at.split('T')[0]} (${v.days_left}일 남음)`
                                : v.used_at ? `사용일: ${v.used_at.split('T')[0]}` : `만료: ${v.expires_at.split('T')[0]}`
                            }
                        </div>

                        {/* 응원 메시지 */}
                        {v.cheer_message && (
                            <div style={{ color: '#888', fontSize: '12px', fontStyle: 'italic', marginBottom: '12px' }}>
                                "{v.cheer_message}"
                            </div>
                        )}

                        {/* 사용하기 버튼 */}
                        {isActive && (
                            <Link to={`/donzzul/vouchers/${v.code}/use`}
                                style={{
                                    display: 'block', width: '100%', padding: '12px',
                                    borderRadius: '10px', textAlign: 'center',
                                    background: '#f472b6', color: '#fff',
                                    textDecoration: 'none', fontWeight: 'bold', fontSize: '15px',
                                    boxSizing: 'border-box',
                                }}>
                                🏓 사용하기
                            </Link>
                        )}
                    </div>
                )
            })}
        </div>
    )
}
