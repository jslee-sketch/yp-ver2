import { useEffect, useRef, useState } from 'react'

interface Props {
    active: boolean
    finalPrice?: number
    onComplete?: () => void
    duration?: number
}

export default function MatrixCodeRain({ active, finalPrice, onComplete, duration = 3500 }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const [phase, setPhase] = useState<'rain' | 'converge' | 'reveal' | 'done'>('rain')
    const [revealed, setRevealed] = useState(false)

    useEffect(() => {
        if (!active) { setPhase('rain'); setRevealed(false); return }

        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        canvas.width = canvas.offsetWidth * 2
        canvas.height = canvas.offsetHeight * 2
        ctx.scale(2, 2)

        const width = canvas.offsetWidth
        const height = canvas.offsetHeight

        const fontSize = 14
        const columns = Math.floor(width / fontSize)
        const drops: number[] = Array(columns).fill(0)
        const speeds: number[] = Array(columns).fill(0).map(() => 0.5 + Math.random() * 1.5)

        const priceStrings = [
            '₩1,230,000', '₩980,000', '₩1,150,000', '$899',
            '₩1,300,000', '¥89,000', '₩950,000', '€750',
            '₩1,050,000', '$1,099', '₩1,180,000', '₩890,000',
        ]

        let startTime = Date.now()
        let animId: number
        let running = true

        const draw = () => {
            if (!running) return
            const elapsed = Date.now() - startTime
            const progress = Math.min(elapsed / duration, 1)

            if (progress < 0.65) {
                setPhase('rain')
            } else if (progress < 0.85) {
                setPhase('converge')
            } else if (progress < 1) {
                setPhase('reveal')
            } else {
                setPhase('done')
                setRevealed(true)
                if (onComplete) onComplete()
                return
            }

            ctx.fillStyle = progress < 0.85
                ? 'rgba(15, 15, 26, 0.08)'
                : 'rgba(15, 15, 26, 0.15)'
            ctx.fillRect(0, 0, width, height)

            if (progress < 0.85) {
                const speedMult = progress < 0.65
                    ? 1 + progress * 2
                    : Math.max(0.1, 1 - (progress - 0.65) * 5)

                for (let i = 0; i < columns; i++) {
                    const brightness = 150 + Math.floor(Math.random() * 105)
                    ctx.fillStyle = `rgb(0, ${brightness}, ${Math.floor(brightness * 0.3)})`
                    ctx.font = `${fontSize}px monospace`

                    let char: string
                    if (progress < 0.65) {
                        const priceStr = priceStrings[Math.floor(Math.random() * priceStrings.length)]
                        char = priceStr[Math.floor(Math.random() * priceStr.length)]
                    } else {
                        const finalStr = `₩${(finalPrice || 0).toLocaleString()}`
                        char = finalStr[Math.floor(Math.random() * finalStr.length)]
                    }

                    ctx.fillText(char, i * fontSize, drops[i] * fontSize)

                    if (drops[i] * fontSize > height && Math.random() > 0.95) {
                        drops[i] = 0
                    }
                    drops[i] += speeds[i] * speedMult
                }
            }

            if (progress >= 0.65 && progress < 0.85) {
                const convergeProg = (progress - 0.65) / 0.2
                const centerX = width / 2
                const centerY = height / 2
                const radius = (1 - convergeProg) * Math.max(width, height) * 0.5

                const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius)
                gradient.addColorStop(0, `rgba(74, 222, 128, ${convergeProg * 0.3})`)
                gradient.addColorStop(1, 'rgba(74, 222, 128, 0)')
                ctx.fillStyle = gradient
                ctx.fillRect(0, 0, width, height)
            }

            animId = requestAnimationFrame(draw)
        }

        animId = requestAnimationFrame(draw)

        return () => { running = false; cancelAnimationFrame(animId) }
    }, [active, finalPrice, duration, onComplete])

    useEffect(() => {
        if (phase === 'reveal') {
            try {
                const enabled = localStorage.getItem('sound_enabled') === 'true'
                if (!enabled) return
                const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
                const osc = ctx.createOscillator()
                const gain = ctx.createGain()
                osc.type = 'sine'
                osc.connect(gain)
                gain.connect(ctx.destination)
                osc.frequency.setValueAtTime(120, ctx.currentTime)
                osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 1.5)
                gain.gain.setValueAtTime(0.15, ctx.currentTime)
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 2)
                osc.start(ctx.currentTime)
                osc.stop(ctx.currentTime + 2)
            } catch {}
        }
    }, [phase])

    if (!active && !revealed) return null

    return (
        <div style={{
            position: 'relative', width: '100%', height: '200px',
            borderRadius: '12px', overflow: 'hidden',
            background: '#0f0f1a',
            border: '1px solid rgba(74, 222, 128, 0.2)',
            marginBottom: '16px',
        }}>
            <canvas ref={canvasRef} style={{
                width: '100%', height: '100%',
                opacity: phase === 'done' ? 0 : 1,
                transition: 'opacity 0.5s',
            }} />

            <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                opacity: (phase === 'reveal' || phase === 'done') ? 1 : 0,
                transform: (phase === 'reveal' || phase === 'done') ? 'scale(1)' : 'scale(0.8)',
                transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>
                <div style={{
                    fontSize: '36px', fontWeight: 'bold', color: '#4ade80',
                    textShadow: '0 0 20px rgba(74, 222, 128, 0.5), 0 0 40px rgba(74, 222, 128, 0.3)',
                    fontFamily: 'monospace',
                }}>
                    ₩ {(finalPrice || 0).toLocaleString()}
                </div>
                <div style={{
                    fontSize: '13px', color: '#4ade80', marginTop: '8px',
                    letterSpacing: '3px',
                }}>
                    ━━━ 시장가 분석 완료 ━━━
                </div>
                <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                    네이버쇼핑 기준
                </div>
            </div>

            {phase === 'rain' && (
                <div style={{
                    position: 'absolute', bottom: '12px', left: '50%',
                    transform: 'translateX(-50%)',
                    fontSize: '12px', color: '#4ade80',
                    fontFamily: 'monospace', letterSpacing: '2px',
                    animation: 'pulse 1.5s infinite',
                }}>
                    AI 시장가 분석 중...
                </div>
            )}
        </div>
    )
}
