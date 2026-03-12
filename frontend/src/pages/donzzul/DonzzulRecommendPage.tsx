import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''

const CATEGORIES = [
    '음식점', '카페', '분식', '국밥/탕', '한식', '중식',
    '일식', '베이커리', '치킨', '족발/보쌈', '기타'
]

export default function DonzzulRecommendPage() {
    const navigate = useNavigate()
    const [step, setStep] = useState(1)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    // Step 1: 가게 정보
    const [storeName, setStoreName] = useState('')
    const [storeAddress, setStoreAddress] = useState('')
    const [storePhone, setStorePhone] = useState('')
    const [storeCategory, setStoreCategory] = useState('')

    // Step 2: 사장님 정보
    const [ownerName, setOwnerName] = useState('')
    const [ownerPhone, setOwnerPhone] = useState('')
    const [ownerConsent, setOwnerConsent] = useState(false)
    const [businessNumber, setBusinessNumber] = useState('')

    // Step 3: 정산 계좌
    const [bankName, setBankName] = useState('')
    const [accountNumber, setAccountNumber] = useState('')
    const [accountHolder, setAccountHolder] = useState('')

    // Step 4: 사연
    const [storyText, setStoryText] = useState('')
    const [youtubeUrl, setYoutubeUrl] = useState('')

    const validateStep = (s: number): boolean => {
        setError('')
        if (s === 1) {
            if (!storeName.trim()) { setError('가게명을 입력해주세요'); return false }
            if (!storeAddress.trim()) { setError('주소를 입력해주세요'); return false }
            if (!storePhone.trim()) { setError('전화번호를 입력해주세요'); return false }
        }
        if (s === 2) {
            if (!ownerName.trim()) { setError('대표자명을 입력해주세요'); return false }
            if (!ownerPhone.trim()) { setError('대표자 연락처를 입력해주세요'); return false }
            if (!ownerConsent) { setError('사장님 동의를 확인해주세요'); return false }
        }
        if (s === 3) {
            if (!bankName.trim()) { setError('은행명을 입력해주세요'); return false }
            if (!accountNumber.trim()) { setError('계좌번호를 입력해주세요'); return false }
            if (!accountHolder.trim()) { setError('예금주를 입력해주세요'); return false }
        }
        if (s === 4) {
            if (storyText.trim().length < 50) { setError('사연은 최소 50자 이상 작성해주세요'); return false }
        }
        return true
    }

    const nextStep = () => {
        if (validateStep(step)) setStep(step + 1)
    }

    const submit = async () => {
        if (!validateStep(4)) return
        setLoading(true)
        setError('')

        try {
            const token = localStorage.getItem('token')
            const user = JSON.parse(localStorage.getItem('user') || '{}')

            const r = await fetch(`${API}/donzzul/stores`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    store_name: storeName,
                    store_address: storeAddress,
                    store_phone: storePhone,
                    store_category: storeCategory,
                    owner_name: ownerName,
                    owner_phone: ownerPhone,
                    owner_consent: ownerConsent,
                    business_number: businessNumber,
                    bank_name: bankName,
                    account_number: accountNumber,
                    account_holder: accountHolder,
                    story_text: storyText,
                    youtube_url: youtubeUrl,
                    registered_by_user_id: user.id,
                }),
            })

            if (!r.ok) {
                const err = await r.json()
                setError(err.detail || '등록에 실패했습니다')
                return
            }

            navigate('/donzzul/hero/my-stores')
        } catch {
            setError('네트워크 오류가 발생했습니다')
        } finally {
            setLoading(false)
        }
    }

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '12px 14px', borderRadius: '8px',
        background: '#0f0f1a', color: '#e0e0e0',
        border: '1px solid #2a2a4a', fontSize: '14px',
        marginBottom: '12px', boxSizing: 'border-box',
    }

    const labelStyle: React.CSSProperties = {
        color: '#888', fontSize: '13px', marginBottom: '4px', display: 'block',
    }

    return (
        <div style={{ maxWidth: '500px', margin: '0 auto', padding: '20px' }}>
            <h1 style={{ color: '#f472b6', marginBottom: '8px' }}>💚 가게 추천하기</h1>

            {/* 진행 바 */}
            <div style={{ display: 'flex', gap: '4px', marginBottom: '24px' }}>
                {[1,2,3,4].map(s => (
                    <div key={s} style={{
                        flex: 1, height: '4px', borderRadius: '2px',
                        background: s <= step ? '#f472b6' : '#2a2a4a',
                        transition: 'background 0.3s',
                    }} />
                ))}
            </div>

            {/* Step 1: 가게 정보 */}
            {step === 1 && (
                <div>
                    <h2 style={{ color: '#e0e0e0', marginBottom: '16px' }}>Step 1. 가게 정보</h2>
                    <label style={labelStyle}>가게명 *</label>
                    <input value={storeName} onChange={e => setStoreName(e.target.value)}
                        placeholder="예: 김씨네 40년 국밥" style={inputStyle} />

                    <label style={labelStyle}>가게 주소 *</label>
                    <input value={storeAddress} onChange={e => setStoreAddress(e.target.value)}
                        placeholder="예: 서울 종로구 을지로 123" style={inputStyle} />

                    <label style={labelStyle}>가게 전화번호 *</label>
                    <input value={storePhone} onChange={e => setStorePhone(e.target.value)}
                        placeholder="예: 02-1234-5678" style={inputStyle} />

                    <label style={labelStyle}>카테고리</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
                        {CATEGORIES.map(cat => (
                            <button key={cat} onClick={() => setStoreCategory(cat)}
                                style={{
                                    padding: '6px 14px', borderRadius: '20px',
                                    background: storeCategory === cat ? '#f472b620' : '#0f0f1a',
                                    border: `1px solid ${storeCategory === cat ? '#f472b6' : '#2a2a4a'}`,
                                    color: storeCategory === cat ? '#f472b6' : '#888',
                                    cursor: 'pointer', fontSize: '13px',
                                }}>
                                {cat}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Step 2: 사장님 정보 */}
            {step === 2 && (
                <div>
                    <h2 style={{ color: '#e0e0e0', marginBottom: '16px' }}>Step 2. 사장님 정보</h2>
                    <label style={labelStyle}>대표자 이름 *</label>
                    <input value={ownerName} onChange={e => setOwnerName(e.target.value)}
                        placeholder="실명" style={inputStyle} />

                    <label style={labelStyle}>대표자 연락처 *</label>
                    <input value={ownerPhone} onChange={e => setOwnerPhone(e.target.value)}
                        placeholder="010-xxxx-xxxx" style={inputStyle} />

                    <label style={labelStyle}>사업자등록번호 (있으면)</label>
                    <input value={businessNumber} onChange={e => setBusinessNumber(e.target.value)}
                        placeholder="000-00-00000" style={inputStyle} />

                    <label style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        color: '#e0e0e0', fontSize: '14px', cursor: 'pointer',
                        padding: '12px', background: ownerConsent ? '#f472b610' : '#0f0f1a',
                        borderRadius: '8px', border: `1px solid ${ownerConsent ? '#f472b6' : '#2a2a4a'}`,
                    }}>
                        <input type="checkbox" checked={ownerConsent}
                            onChange={e => setOwnerConsent(e.target.checked)} />
                        사장님 동의를 받았습니다 *
                    </label>
                    <p style={{ color: '#666', fontSize: '11px', marginTop: '4px' }}>
                        사장님의 동의 없이 등록하면 자격이 정지될 수 있습니다.
                    </p>
                </div>
            )}

            {/* Step 3: 정산 계좌 */}
            {step === 3 && (
                <div>
                    <h2 style={{ color: '#e0e0e0', marginBottom: '16px' }}>Step 3. 정산 계좌</h2>
                    <p style={{ color: '#f59e0b', fontSize: '13px', marginBottom: '12px',
                        padding: '10px', background: '#f59e0b10', borderRadius: '8px',
                        border: '1px solid #f59e0b30' }}>
                        반드시 사장님 본인 명의 계좌만 입력해주세요!
                    </p>

                    <label style={labelStyle}>은행명 *</label>
                    <input value={bankName} onChange={e => setBankName(e.target.value)}
                        placeholder="예: 국민은행" style={inputStyle} />

                    <label style={labelStyle}>계좌번호 *</label>
                    <input value={accountNumber} onChange={e => setAccountNumber(e.target.value)}
                        placeholder="숫자만 입력" style={inputStyle} />

                    <label style={labelStyle}>예금주 *</label>
                    <input value={accountHolder} onChange={e => setAccountHolder(e.target.value)}
                        placeholder="사장님 실명과 동일해야 합니다" style={inputStyle} />
                </div>
            )}

            {/* Step 4: 사연 */}
            {step === 4 && (
                <div>
                    <h2 style={{ color: '#e0e0e0', marginBottom: '16px' }}>Step 4. 사연</h2>
                    <label style={labelStyle}>왜 이 가게를 응원해야 할까요? * (최소 50자)</label>
                    <textarea value={storyText} onChange={e => setStoryText(e.target.value)}
                        placeholder="가게의 사연을 적어주세요. 진심이 담긴 이야기가 더 많은 응원을 받아요!"
                        rows={6}
                        style={{
                            ...inputStyle, resize: 'vertical', lineHeight: '1.6',
                            minHeight: '120px',
                        }} />
                    <div style={{ color: storyText.length >= 50 ? '#4ade80' : '#888', fontSize: '12px', textAlign: 'right' }}>
                        {storyText.length}/50자 이상
                    </div>

                    <label style={{ ...labelStyle, marginTop: '12px' }}>유튜브 영상 URL (선택)</label>
                    <input value={youtubeUrl} onChange={e => setYoutubeUrl(e.target.value)}
                        placeholder="https://youtube.com/watch?v=..." style={inputStyle} />
                    {youtubeUrl && (
                        <p style={{ color: '#4ade80', fontSize: '12px' }}>
                            영상이 있으면 투표에 유리해요!
                        </p>
                    )}
                </div>
            )}

            {/* 에러 */}
            {error && (
                <div style={{
                    padding: '10px 14px', borderRadius: '8px',
                    background: '#ef444420', border: '1px solid #ef4444',
                    color: '#ef4444', fontSize: '13px', marginBottom: '12px',
                }}>
                    {error}
                </div>
            )}

            {/* 버튼 */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                {step > 1 && (
                    <button onClick={() => setStep(step - 1)}
                        style={{
                            flex: 1, padding: '14px', borderRadius: '12px',
                            background: '#2a2a4a', color: '#888',
                            border: 'none', cursor: 'pointer', fontSize: '15px',
                        }}>이전</button>
                )}
                {step < 4 ? (
                    <button onClick={nextStep}
                        style={{
                            flex: 1, padding: '14px', borderRadius: '12px',
                            background: '#f472b6', color: '#fff',
                            border: 'none', cursor: 'pointer', fontSize: '15px', fontWeight: 'bold',
                        }}>다음</button>
                ) : (
                    <button onClick={submit} disabled={loading}
                        style={{
                            flex: 1, padding: '14px', borderRadius: '12px',
                            background: loading ? '#666' : '#f472b6', color: '#fff',
                            border: 'none', cursor: 'pointer', fontSize: '15px', fontWeight: 'bold',
                        }}>
                        {loading ? '등록 중...' : '💚 추천 등록하기'}
                    </button>
                )}
            </div>
        </div>
    )
}
