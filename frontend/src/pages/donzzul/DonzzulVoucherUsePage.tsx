import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''

export default function DonzzulVoucherUsePage() {
    const { code } = useParams()
    const navigate = useNavigate()
    const [voucher, setVoucher] = useState<any>(null)
    const [pin, setPin] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [result, setResult] = useState<any>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        const token = localStorage.getItem('token')
        const user = JSON.parse(localStorage.getItem('user') || '{}')
        fetch(`${API}/donzzul/vouchers/my?buyer_id=${user.id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()).then(data => {
            const v = (Array.isArray(data) ? data : []).find((x: any) => x.code === code)
            setVoucher(v)
        })
    }, [code])

    const handleKeyPress = (key: string) => {
        setError('')
        if (key === 'del') {
            setPin(p => p.slice(0, -1))
        } else if (key === 'clear') {
            setPin('')
        } else if (pin.length < 4) {
            setPin(p => p + key)
        }
    }

    const submit = async () => {
        if (pin.length !== 4) return
        setLoading(true)
        setError('')

        const token = localStorage.getItem('token')
        const r = await fetch(`${API}/donzzul/vouchers/${code}/redeem`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ store_pin: pin }),
        })

        if (r.ok) {
            const data = await r.json()
            setSuccess(true)
            setResult(data)
        } else {
            const err = await r.json()
            setError(err.detail || '사용 실패')
            setPin('')
        }
        setLoading(false)
    }

    // 성공 화면
    if (success && result) {
        return (
            <div style={{ maxWidth: '400px', margin: '0 auto', padding: '60px 20px', textAlign: 'center' }}>
                <div style={{
                    width: '80px', height: '80px', borderRadius: '50%',
                    background: '#4ade8020', border: '3px solid #4ade80',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 20px', fontSize: '36px',
                }}>✓</div>
                <h1 style={{ color: '#4ade80', marginBottom: '8px' }}>사용 완료!</h1>
                <p style={{ color: '#e0e0e0', fontSize: '18px', marginBottom: '4px' }}>
                    {result.store_name}
                </p>
                <p style={{ color: '#f472b6', fontSize: '24px', fontWeight: 'bold', marginBottom: '24px' }}>
                    ₩{result.amount?.toLocaleString()}
                </p>
                <p style={{ color: '#888', marginBottom: '24px' }}>감사합니다 💚</p>
                <button onClick={() => navigate('/donzzul/vouchers')}
                    style={{
                        padding: '14px 32px', borderRadius: '12px',
                        background: '#f472b6', color: '#fff',
                        border: 'none', cursor: 'pointer', fontSize: '15px', fontWeight: 'bold',
                    }}>내 상품권함으로</button>
            </div>
        )
    }

    if (!voucher) return <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>로딩 중...</div>

    return (
        <div style={{ maxWidth: '400px', margin: '0 auto', padding: '20px', textAlign: 'center' }}>
            {/* 상품권 정보 */}
            <div style={{
                background: '#1a1a2e', borderRadius: '16px', padding: '24px',
                marginBottom: '24px',
            }}>
                <div style={{ color: '#888', fontSize: '13px', marginBottom: '4px' }}>{voucher.store_name}</div>
                <div style={{ color: '#f472b6', fontSize: '28px', fontWeight: 'bold', marginBottom: '4px' }}>
                    ₩{voucher.amount.toLocaleString()}
                </div>
                <div style={{ color: '#666', fontSize: '12px' }}>{voucher.code}</div>
            </div>

            <div style={{ color: '#e0e0e0', fontSize: '15px', marginBottom: '16px' }}>
                사장님에게 화면을 보여주세요<br/>
                <span style={{ color: '#888', fontSize: '13px' }}>사장님이 비밀번호를 입력합니다</span>
            </div>

            {/* PIN 표시 */}
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginBottom: '20px' }}>
                {[0,1,2,3].map(i => (
                    <div key={i} style={{
                        width: '50px', height: '60px', borderRadius: '12px',
                        background: '#0f0f1a', border: `2px solid ${pin[i] ? '#f472b6' : '#2a2a4a'}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '24px', fontWeight: 'bold', color: '#f472b6',
                    }}>
                        {pin[i] ? '●' : ''}
                    </div>
                ))}
            </div>

            {/* 에러 */}
            {error && (
                <div style={{
                    padding: '10px', borderRadius: '8px',
                    background: '#ef444420', color: '#ef4444',
                    fontSize: '13px', marginBottom: '12px',
                }}>{error}</div>
            )}

            {/* 키패드 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', maxWidth: '280px', margin: '0 auto' }}>
                {['1','2','3','4','5','6','7','8','9','clear','0','del'].map(key => (
                    <button key={key}
                        onClick={() => handleKeyPress(key)}
                        style={{
                            padding: '18px', borderRadius: '12px',
                            background: key === 'clear' || key === 'del' ? '#2a2a4a' : '#1a1a2e',
                            border: '1px solid #2a2a4a', color: '#e0e0e0',
                            fontSize: key === 'clear' || key === 'del' ? '13px' : '20px',
                            fontWeight: 'bold', cursor: 'pointer',
                        }}>
                        {key === 'del' ? '⌫' : key === 'clear' ? 'C' : key}
                    </button>
                ))}
            </div>

            {/* 확인 버튼 */}
            <button onClick={submit}
                disabled={pin.length !== 4 || loading}
                style={{
                    width: '100%', maxWidth: '280px', padding: '16px', borderRadius: '12px',
                    background: pin.length === 4 ? '#f472b6' : '#333',
                    color: pin.length === 4 ? '#fff' : '#666',
                    border: 'none', cursor: pin.length === 4 ? 'pointer' : 'default',
                    fontSize: '16px', fontWeight: 'bold', marginTop: '16px',
                }}>
                {loading ? '확인 중...' : '확인'}
            </button>
        </div>
    )
}
