import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL || ''

export default function AdminDonzzulSettlementsPage() {
    const [settlements, setSettlements] = useState<any[]>([])
    const [stores, setStores] = useState<any[]>([])
    const [filter, setFilter] = useState('')
    const [selectedId, setSelectedId] = useState<number | null>(null)
    const [detail, setDetail] = useState<any>(null)

    const loadSettlements = () => {
        const token = localStorage.getItem('token')
        const url = filter
            ? `${API}/donzzul/settlements?status=${filter}`
            : `${API}/donzzul/settlements`
        fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(r => r.json()).then(data => setSettlements(Array.isArray(data) ? data : []))
    }

    const loadStores = () => {
        const token = localStorage.getItem('token')
        fetch(`${API}/donzzul/stores?status=APPROVED`, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(r => r.json()).then(data => setStores(Array.isArray(data) ? data : []))
    }

    useEffect(() => { loadSettlements(); loadStores() }, [filter])

    const createSettlement = async (storeId: number) => {
        const token = localStorage.getItem('token')
        const r = await fetch(`${API}/donzzul/settlements/create`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ store_id: storeId }),
        })
        const data = await r.json()
        if (data.error) {
            alert(data.error)
        } else {
            alert(`정산 생성! ${data.voucher_count}건 / ${data.payout_amount.toLocaleString()}원`)
            loadSettlements()
        }
    }

    const processSettlement = async (settlementId: number, action: string) => {
        const token = localStorage.getItem('token')
        const user = JSON.parse(localStorage.getItem('user') || '{}')
        await fetch(`${API}/donzzul/settlements/${settlementId}/process`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, admin_id: user.id }),
        })
        loadSettlements()
        if (selectedId === settlementId) loadDetail(settlementId)
    }

    const loadDetail = (id: number) => {
        setSelectedId(id)
        const token = localStorage.getItem('token')
        fetch(`${API}/donzzul/settlements/${id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()).then(setDetail)
    }

    const runBatch = async (type: string) => {
        const token = localStorage.getItem('token')
        const r = await fetch(`${API}/donzzul/batch/${type}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
        })
        const data = await r.json()
        alert(JSON.stringify(data, null, 2))
    }

    const STATUS_COLORS: Record<string, string> = {
        PENDING: '#f59e0b', APPROVED: '#60a5fa', PAID: '#4ade80', REJECTED: '#ef4444',
    }

    return (
        <div style={{ padding: '20px' }}>
            <h1 style={{ color: '#f472b6', marginBottom: '16px' }}>💚 돈쭐 정산</h1>

            {/* 배치 실행 버튼 */}
            <div style={{
                display: 'flex', gap: '8px', marginBottom: '16px',
                padding: '12px', background: '#1a1a2e', borderRadius: '8px', flexWrap: 'wrap',
            }}>
                <span style={{ color: '#888', fontSize: '13px', lineHeight: '32px' }}>배치 실행:</span>
                <button onClick={() => runBatch('expiry')}
                    style={{ padding: '6px 14px', borderRadius: '6px', background: '#f59e0b20', border: '1px solid #f59e0b', color: '#f59e0b', cursor: 'pointer', fontSize: '12px' }}>
                    만료 처리
                </button>
                <button onClick={() => runBatch('expiry-warning')}
                    style={{ padding: '6px 14px', borderRadius: '6px', background: '#60a5fa20', border: '1px solid #60a5fa', color: '#60a5fa', cursor: 'pointer', fontSize: '12px' }}>
                    만료 알림
                </button>
                <button onClick={() => runBatch('deal-expiry')}
                    style={{ padding: '6px 14px', borderRadius: '6px', background: '#f472b620', border: '1px solid #f472b6', color: '#f472b6', cursor: 'pointer', fontSize: '12px' }}>
                    딜 마감
                </button>
            </div>

            {/* 가게별 정산 생성 */}
            <div style={{
                padding: '12px', background: '#1a1a2e', borderRadius: '8px',
                marginBottom: '16px',
            }}>
                <div style={{ color: '#888', fontSize: '13px', marginBottom: '8px' }}>
                    가게별 정산 생성:
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {stores.map(s => (
                        <button key={s.id} onClick={() => createSettlement(s.id)}
                            style={{
                                padding: '6px 12px', borderRadius: '6px',
                                background: '#0f0f1a', border: '1px solid #2a2a4a',
                                color: '#e0e0e0', cursor: 'pointer', fontSize: '12px',
                            }}>
                            {s.store_name}
                        </button>
                    ))}
                </div>
            </div>

            {/* 필터 */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                {['', 'PENDING', 'APPROVED', 'PAID', 'REJECTED'].map(f => (
                    <button key={f} onClick={() => setFilter(f)}
                        style={{
                            padding: '6px 14px', borderRadius: '6px',
                            background: filter === f ? '#f472b620' : '#1a1a2e',
                            border: `1px solid ${filter === f ? '#f472b6' : '#2a2a4a'}`,
                            color: filter === f ? '#f472b6' : '#888',
                            cursor: 'pointer', fontSize: '12px',
                        }}>
                        {f || '전체'}
                    </button>
                ))}
            </div>

            {/* 정산 목록 */}
            <div style={{ display: 'flex', gap: '16px' }}>
                <div style={{ flex: 1 }}>
                    {settlements.map(s => (
                        <div key={s.id}
                            onClick={() => loadDetail(s.id)}
                            style={{
                                background: selectedId === s.id ? '#2a2a4a' : '#1a1a2e',
                                borderRadius: '8px', padding: '12px', marginBottom: '4px',
                                cursor: 'pointer',
                                borderLeft: `3px solid ${STATUS_COLORS[s.status] || '#888'}`,
                            }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: '#e0e0e0', fontWeight: 'bold' }}>
                                    DS-{s.id}
                                </span>
                                <span style={{
                                    padding: '2px 8px', borderRadius: '8px', fontSize: '11px',
                                    background: `${STATUS_COLORS[s.status] || '#888'}20`,
                                    color: STATUS_COLORS[s.status] || '#888',
                                }}>{s.status}</span>
                            </div>
                            <div style={{ color: '#888', fontSize: '12px', marginTop: '4px' }}>
                                {s.payout_amount?.toLocaleString()}원 | {s.voucher_count}건
                            </div>

                            {/* 액션 버튼 */}
                            <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                                {s.status === 'PENDING' && (
                                    <button onClick={e => { e.stopPropagation(); processSettlement(s.id, 'approve') }}
                                        style={{ padding: '4px 10px', borderRadius: '6px', background: '#4ade8020', border: '1px solid #4ade80', color: '#4ade80', cursor: 'pointer', fontSize: '11px' }}>
                                        승인
                                    </button>
                                )}
                                {s.status === 'APPROVED' && (
                                    <button onClick={e => { e.stopPropagation(); processSettlement(s.id, 'pay') }}
                                        style={{ padding: '4px 10px', borderRadius: '6px', background: '#60a5fa20', border: '1px solid #60a5fa', color: '#60a5fa', cursor: 'pointer', fontSize: '11px' }}>
                                        지급 완료
                                    </button>
                                )}
                                {s.status === 'PENDING' && (
                                    <button onClick={e => { e.stopPropagation(); processSettlement(s.id, 'reject') }}
                                        style={{ padding: '4px 10px', borderRadius: '6px', background: '#ef444420', border: '1px solid #ef4444', color: '#ef4444', cursor: 'pointer', fontSize: '11px' }}>
                                        거절
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                    {settlements.length === 0 && (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>정산 내역이 없습니다</div>
                    )}
                </div>

                {/* 상세 패널 */}
                {detail && (
                    <div style={{ width: '350px', background: '#1a1a2e', borderRadius: '12px', padding: '16px' }}>
                        <h3 style={{ color: '#f472b6', marginBottom: '12px' }}>
                            DS-{detail.settlement?.id} 상세
                        </h3>
                        <div style={{ color: '#e0e0e0', fontSize: '13px', lineHeight: '2' }}>
                            가게: {detail.store?.store_name}<br/>
                            총액: {detail.settlement?.total_amount?.toLocaleString()}원<br/>
                            ├ 사용분: {detail.settlement?.used_amount?.toLocaleString()}원<br/>
                            ├ 만료기부: {detail.settlement?.donated_amount?.toLocaleString()}원<br/>
                            ├ 수수료: 0원<br/>
                            └ 지급액: <strong style={{ color: '#4ade80' }}>{detail.settlement?.payout_amount?.toLocaleString()}원</strong><br/>
                            계좌: {detail.settlement?.bank_name} {detail.settlement?.account_number}<br/>
                            예금주: {detail.settlement?.account_holder}<br/>
                            상품권: {detail.vouchers?.length}건
                        </div>

                        <div style={{ marginTop: '12px', maxHeight: '200px', overflow: 'auto' }}>
                            {detail.vouchers?.map((v: any) => (
                                <div key={v.id} style={{
                                    padding: '6px 8px', borderRadius: '6px',
                                    background: '#0f0f1a', marginBottom: '2px',
                                    display: 'flex', justifyContent: 'space-between',
                                    fontSize: '12px',
                                }}>
                                    <span style={{ color: '#888' }}>{v.code}</span>
                                    <span style={{ color: v.status === 'USED' ? '#4ade80' : '#f472b6' }}>
                                        {v.amount?.toLocaleString()}원 ({v.status === 'USED' ? '사용' : '기부'})
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
