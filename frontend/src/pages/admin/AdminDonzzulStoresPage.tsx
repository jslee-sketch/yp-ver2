import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL || ''

export default function AdminDonzzulStoresPage() {
    const [stores, setStores] = useState<any[]>([])
    const [filter, setFilter] = useState('REVIEWING')
    const [selectedStore, setSelectedStore] = useState<any>(null)
    const [verifyNotes, setVerifyNotes] = useState('')
    const [pin, setPin] = useState('')
    const [consentMethod, setConsentMethod] = useState('phone')
    const [accountVerified, setAccountVerified] = useState(false)
    const [loading, setLoading] = useState(false)

    const loadStores = () => {
        const token = localStorage.getItem('token')
        const url = filter ? `${API}/donzzul/stores?status=${filter}` : `${API}/donzzul/stores`
        fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(r => r.json())
            .then(data => setStores(Array.isArray(data) ? data : []))
    }

    useEffect(() => { loadStores() }, [filter])

    const approve = async (storeId: number) => {
        if (!pin || pin.length !== 4) {
            alert('사장님 비밀번호(4자리)를 입력해주세요')
            return
        }
        setLoading(true)
        const token = localStorage.getItem('token')
        const user = JSON.parse(localStorage.getItem('user') || '{}')

        await fetch(`${API}/donzzul/stores/${storeId}/verify`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'approve',
                admin_id: user.id,
                notes: verifyNotes,
                consent_method: consentMethod,
                account_verified: accountVerified,
            }),
        })

        await fetch(`${API}/donzzul/stores/${storeId}/set-pin`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin }),
        })

        setSelectedStore(null)
        setVerifyNotes('')
        setPin('')
        setAccountVerified(false)
        setLoading(false)
        loadStores()
    }

    const reject = async (storeId: number) => {
        if (!verifyNotes.trim()) {
            alert('거절 사유를 입력해주세요')
            return
        }
        const token = localStorage.getItem('token')
        await fetch(`${API}/donzzul/stores/${storeId}/verify`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'reject', notes: verifyNotes }),
        })
        setSelectedStore(null)
        setVerifyNotes('')
        loadStores()
    }

    return (
        <div style={{ padding: '20px' }}>
            <h1 style={{ color: '#f472b6', marginBottom: '16px' }}>💚 돈쭐 가게 관리</h1>

            {/* 필터 */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
                {['REVIEWING', 'APPROVED', 'REJECTED', ''].map(f => (
                    <button key={f} onClick={() => setFilter(f)}
                        style={{
                            padding: '8px 16px', borderRadius: '8px',
                            background: filter === f ? '#f472b620' : '#1a1a2e',
                            border: `1px solid ${filter === f ? '#f472b6' : '#2a2a4a'}`,
                            color: filter === f ? '#f472b6' : '#888',
                            cursor: 'pointer', fontSize: '13px',
                        }}>
                        {f === 'REVIEWING' ? '검증 대기' : f === 'APPROVED' ? '승인' : f === 'REJECTED' ? '거절' : '전체'}
                    </button>
                ))}
            </div>

            {/* 가게 목록 */}
            {stores.map(store => (
                <div key={store.id} style={{
                    background: '#1a1a2e', borderRadius: '12px', padding: '16px',
                    marginBottom: '8px',
                    border: selectedStore?.id === store.id ? '1px solid #f472b6' : '1px solid transparent',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ color: '#e0e0e0', fontWeight: 'bold', fontSize: '15px' }}>
                            {store.store_name}
                        </span>
                        <span style={{
                            padding: '2px 10px', borderRadius: '12px', fontSize: '12px',
                            background: store.status === 'REVIEWING' ? '#f59e0b20' : store.status === 'APPROVED' ? '#4ade8020' : '#ef444420',
                            color: store.status === 'REVIEWING' ? '#f59e0b' : store.status === 'APPROVED' ? '#4ade80' : '#ef4444',
                        }}>{store.status}</span>
                    </div>

                    <div style={{ color: '#888', fontSize: '13px', lineHeight: '1.6' }}>
                        {store.store_address}<br/>
                        가게: {store.store_phone} | 대표: {store.owner_name} ({store.owner_phone})<br/>
                        {store.bank_name} {store.account_number} ({store.account_holder})<br/>
                        {store.business_number && <>사업자: {store.business_number}<br/></>}
                        {store.youtube_url && <><a href={store.youtube_url} target="_blank" rel="noreferrer" style={{color:'#60a5fa'}}>영상 보기</a><br/></>}
                    </div>

                    <div style={{
                        marginTop: '8px', padding: '10px', borderRadius: '8px',
                        background: '#0f0f1a', color: '#e0e0e0', fontSize: '13px',
                        lineHeight: '1.6',
                    }}>
                        {store.story_text}
                    </div>

                    {store.status === 'REVIEWING' && (
                        <div style={{ marginTop: '12px' }}>
                            {selectedStore?.id === store.id ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {/* 검증 체크리스트 */}
                                    <div style={{ padding: '12px', background: '#0f0f1a', borderRadius: '8px' }}>
                                        <div style={{ color: '#f472b6', fontSize: '13px', fontWeight: 'bold', marginBottom: '8px' }}>
                                            검증 체크리스트
                                        </div>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#e0e0e0', fontSize: '13px', marginBottom: '4px' }}>
                                            <input type="checkbox" /> 네이버지도에서 실존 가게 확인
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#e0e0e0', fontSize: '13px', marginBottom: '4px' }}>
                                            <input type="checkbox" /> 대표자 전화 확인
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#e0e0e0', fontSize: '13px', marginBottom: '4px' }}>
                                            <input type="checkbox" checked={accountVerified}
                                                onChange={e => setAccountVerified(e.target.checked)} />
                                            계좌 예금주 = 대표자명 일치
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#e0e0e0', fontSize: '13px', marginBottom: '4px' }}>
                                            <input type="checkbox" /> 사연 적절성 확인
                                        </label>
                                    </div>

                                    {/* 동의 방법 */}
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        {['phone', 'visit', 'kakaotalk'].map(m => (
                                            <button key={m} onClick={() => setConsentMethod(m)}
                                                style={{
                                                    padding: '6px 12px', borderRadius: '6px',
                                                    background: consentMethod === m ? '#4ade8020' : '#0f0f1a',
                                                    border: `1px solid ${consentMethod === m ? '#4ade80' : '#2a2a4a'}`,
                                                    color: consentMethod === m ? '#4ade80' : '#888',
                                                    cursor: 'pointer', fontSize: '12px',
                                                }}>
                                                {m === 'phone' ? '전화' : m === 'visit' ? '방문' : '카톡'}
                                            </button>
                                        ))}
                                    </div>

                                    {/* 사장님 비밀번호 */}
                                    <div>
                                        <label style={{ color: '#888', fontSize: '12px' }}>
                                            사장님 비밀번호 (4자리)
                                        </label>
                                        <input value={pin} onChange={e => setPin(e.target.value.replace(/\D/g,'').slice(0,4))}
                                            placeholder="4자리 숫자"
                                            style={{
                                                width: '120px', padding: '8px 12px', borderRadius: '8px',
                                                background: '#0f0f1a', color: '#e0e0e0',
                                                border: '1px solid #2a2a4a', fontSize: '18px',
                                                letterSpacing: '8px', textAlign: 'center',
                                            }} />
                                    </div>

                                    {/* 메모 */}
                                    <textarea value={verifyNotes} onChange={e => setVerifyNotes(e.target.value)}
                                        placeholder="검증 메모 (승인 시 선택, 거절 시 필수)"
                                        rows={2}
                                        style={{
                                            width: '100%', padding: '10px', borderRadius: '8px',
                                            background: '#0f0f1a', color: '#e0e0e0',
                                            border: '1px solid #2a2a4a', fontSize: '13px',
                                            resize: 'vertical', boxSizing: 'border-box',
                                        }} />

                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        <button onClick={() => approve(store.id)} disabled={loading}
                                            style={{
                                                flex: 1, padding: '10px', borderRadius: '8px',
                                                background: '#4ade80', color: '#000',
                                                border: 'none', cursor: 'pointer', fontWeight: 'bold',
                                            }}>승인</button>
                                        <button onClick={() => reject(store.id)}
                                            style={{
                                                flex: 1, padding: '10px', borderRadius: '8px',
                                                background: '#ef4444', color: '#fff',
                                                border: 'none', cursor: 'pointer', fontWeight: 'bold',
                                            }}>거절</button>
                                        <button onClick={() => setSelectedStore(null)}
                                            style={{
                                                padding: '10px 16px', borderRadius: '8px',
                                                background: '#2a2a4a', color: '#888',
                                                border: 'none', cursor: 'pointer',
                                            }}>취소</button>
                                    </div>
                                </div>
                            ) : (
                                <button onClick={() => setSelectedStore(store)}
                                    style={{
                                        padding: '10px 20px', borderRadius: '8px',
                                        background: '#f472b620', color: '#f472b6',
                                        border: '1px solid #f472b6', cursor: 'pointer',
                                        fontSize: '13px', fontWeight: 'bold',
                                    }}>검증하기</button>
                            )}
                        </div>
                    )}
                </div>
            ))}

            {stores.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                    {filter === 'REVIEWING' ? '검증 대기 중인 가게가 없습니다.' : '가게가 없습니다.'}
                </div>
            )}
        </div>
    )
}
