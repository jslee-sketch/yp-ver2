import { useState, useEffect } from 'react'

export default function AuctionHammer({ active, onComplete }: { active: boolean, onComplete?: () => void }) {
    const [count, setCount] = useState(3)
    const [smashed, setSmashed] = useState(false)

    useEffect(() => {
        if (!active) { setCount(3); setSmashed(false); return }

        const timers = [
            setTimeout(() => setCount(2), 1000),
            setTimeout(() => setCount(1), 2000),
            setTimeout(() => {
                setSmashed(true)
                document.body.style.animation = 'shake 0.3s'
                setTimeout(() => { document.body.style.animation = '' }, 300)
                playHammer()
                if (onComplete) setTimeout(onComplete, 1000)
            }, 3000),
        ]

        return () => timers.forEach(clearTimeout)
    }, [active, onComplete])

    const playHammer = () => {
        try {
            const enabled = localStorage.getItem('sound_enabled') === 'true'
            if (!enabled) return
            const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
            const osc1 = ctx.createOscillator()
            const gain1 = ctx.createGain()
            osc1.type = 'sine'
            osc1.connect(gain1)
            gain1.connect(ctx.destination)
            osc1.frequency.setValueAtTime(80, ctx.currentTime)
            gain1.gain.setValueAtTime(0.2, ctx.currentTime)
            gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5)
            osc1.start(ctx.currentTime)
            osc1.stop(ctx.currentTime + 0.5)

            const osc2 = ctx.createOscillator()
            const gain2 = ctx.createGain()
            osc2.type = 'triangle'
            osc2.connect(gain2)
            gain2.connect(ctx.destination)
            osc2.frequency.setValueAtTime(400, ctx.currentTime + 0.02)
            gain2.gain.setValueAtTime(0.1, ctx.currentTime + 0.02)
            gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2)
            osc2.start(ctx.currentTime + 0.02)
            osc2.stop(ctx.currentTime + 0.2)
        } catch {}
    }

    if (!active) return null

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
        }}>
            {!smashed ? (
                <div key={count} style={{
                    fontSize: '120px', fontWeight: 'bold',
                    color: count === 1 ? '#ef4444' : count === 2 ? '#f59e0b' : '#4ade80',
                    fontFamily: 'monospace',
                    animation: 'countUp 0.8s ease-out',
                    textShadow: `0 0 40px ${count === 1 ? '#ef4444' : count === 2 ? '#f59e0b' : '#4ade80'}`,
                }}>
                    {count}
                </div>
            ) : (
                <div style={{ textAlign: 'center', animation: 'fadeInUp 0.5s ease-out' }}>
                    <div style={{ fontSize: '80px', marginBottom: '16px' }}>🔨</div>
                    <div style={{
                        fontSize: '32px', fontWeight: 'bold', color: '#4ade80',
                        textShadow: '0 0 20px rgba(74, 222, 128, 0.5)',
                    }}>딜 마감!</div>
                </div>
            )}
        </div>
    )
}
