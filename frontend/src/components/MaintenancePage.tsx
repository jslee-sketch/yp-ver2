import { useState } from 'react'

export default function MaintenancePage({ onAccessGranted }: { onAccessGranted: () => void }) {
    const [email, setEmail] = useState('')
    const [submitted, setSubmitted] = useState(false)

    return (
        <div style={{
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            padding: '20px',
        }}>
            {/* 로고 */}
            <h1 style={{
                fontSize: '64px', fontWeight: 'bold',
                color: '#4ade80', marginBottom: '8px',
            }}>역핑</h1>
            <p style={{
                color: '#60a5fa', fontSize: '18px',
                marginBottom: '40px', letterSpacing: '2px',
            }}>YEOKPING</p>

            {/* 메인 메시지 */}
            <div style={{
                background: '#1a1a2e', borderRadius: '20px',
                padding: '40px', maxWidth: '500px', width: '100%',
                textAlign: 'center', border: '1px solid #2a2a4a',
            }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🏓</div>
                <h2 style={{ color: '#e0e0e0', fontSize: '24px', marginBottom: '12px' }}>
                    서비스 준비 중입니다
                </h2>
                <p style={{ color: '#888', fontSize: '15px', lineHeight: '1.6', marginBottom: '24px' }}>
                    소비자가 가격을 제안하는 역경매 플랫폼<br/>
                    <strong style={{ color: '#4ade80' }}>역핑</strong>이 곧 찾아갑니다!
                </p>

                {/* 사전 등록 */}
                {!submitted ? (
                    <div>
                        <p style={{ color: '#888', fontSize: '13px', marginBottom: '12px' }}>
                            오픈 알림을 받고 싶으시면 이메일을 남겨주세요!
                        </p>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <input
                                type="email"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                placeholder="이메일 주소"
                                style={{
                                    flex: 1, padding: '12px 16px', borderRadius: '12px',
                                    background: '#0f0f1a', color: '#e0e0e0',
                                    border: '1px solid #2a2a4a', fontSize: '14px',
                                    outline: 'none',
                                }}
                                onKeyDown={e => {
                                    if (e.key === 'Enter' && email.includes('@')) {
                                        (e.target as HTMLInputElement).blur()
                                        fetch('/api/preregister', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ email }),
                                        }).catch(() => {})
                                        setSubmitted(true)
                                    }
                                }}
                            />
                            <button
                                onClick={async () => {
                                    if (!email.includes('@')) return
                                    try {
                                        await fetch('/api/preregister', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ email }),
                                        })
                                    } catch {}
                                    setSubmitted(true)
                                }}
                                style={{
                                    padding: '12px 20px', borderRadius: '12px',
                                    background: '#4ade80', color: '#000',
                                    border: 'none', fontWeight: 'bold',
                                    cursor: 'pointer', fontSize: '14px',
                                    whiteSpace: 'nowrap',
                                }}
                            >알림 받기</button>
                        </div>
                    </div>
                ) : (
                    <div style={{
                        padding: '16px', borderRadius: '12px',
                        background: 'rgba(74,222,128,0.12)', border: '1px solid #4ade80',
                    }}>
                        <p style={{ color: '#4ade80', fontWeight: 'bold', margin: 0 }}>
                            등록 완료! 오픈 시 알려드릴게요.
                        </p>
                    </div>
                )}
            </div>

            {/* 하단 */}
            <p style={{
                color: '#444', fontSize: '12px',
                marginTop: '40px',
            }}>
                &copy; 2026 (주)텔러스테크 &middot; 역핑
            </p>
        </div>
    )
}
