import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL || ''

const STATUS_MAP: Record<string, { label: string, color: string }> = {
    REVIEWING: { label: '검증 대기', color: '#f59e0b' },
    APPROVED: { label: '승인', color: '#4ade80' },
    REJECTED: { label: '거절', color: '#ef4444' },
    OPEN: { label: '오픈', color: '#60a5fa' },
    CLOSED: { label: '종료', color: '#888' },
}

export default function DonzzulMyStoresPage() {
    const [stores, setStores] = useState<any[]>([])

    useEffect(() => {
        const token = localStorage.getItem('token')
        fetch(`${API}/donzzul/stores`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()).then(data => {
            setStores(Array.isArray(data) ? data : [])
        })
    }, [])

    return (
        <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px' }}>
            <h1 style={{ color: '#f472b6', marginBottom: '16px' }}>내가 추천한 가게</h1>

            {stores.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                    아직 추천한 가게가 없어요.<br/>
                    <a href="/donzzul/hero/recommend" style={{ color: '#f472b6' }}>
                        첫 가게를 추천해보세요! 💚
                    </a>
                </div>
            )}

            {stores.map(store => {
                const status = STATUS_MAP[store.status] || { label: store.status, color: '#888' }
                return (
                    <div key={store.id} style={{
                        background: '#1a1a2e', borderRadius: '12px', padding: '16px',
                        marginBottom: '8px',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                            <span style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{store.store_name}</span>
                            <span style={{
                                padding: '2px 10px', borderRadius: '12px',
                                background: `${status.color}20`, color: status.color,
                                fontSize: '12px',
                            }}>{status.label}</span>
                        </div>
                        <div style={{ color: '#888', fontSize: '13px' }}>
                            {store.store_address}
                        </div>
                        {store.status === 'REJECTED' && store.verification_notes && (
                            <div style={{
                                marginTop: '8px', padding: '8px', borderRadius: '6px',
                                background: '#ef444410', color: '#ef4444', fontSize: '12px',
                            }}>
                                거절 사유: {store.verification_notes}
                            </div>
                        )}
                    </div>
                )
            })}
        </div>
    )
}
