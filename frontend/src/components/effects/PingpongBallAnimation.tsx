import { useEffect, useRef } from 'react'

interface Props {
    active: boolean
    size?: number
}

export default function PingpongBallAnimation({ active, size = 60 }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null)

    useEffect(() => {
        if (!active) return
        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        canvas.width = size * 3 * 2
        canvas.height = size * 2
        ctx.scale(2, 2)

        const w = size * 3
        const h = size

        let ballX = size * 0.3
        let ballY = h / 2
        let dx = 2.5
        let dy = 0
        let paddleLeftY = h / 2
        let paddleRightY = h / 2
        let running = true

        const playPong = () => {
            try {
                const enabled = localStorage.getItem('sound_enabled') === 'true'
                if (!enabled) return
                const actx = new (window.AudioContext || (window as any).webkitAudioContext)()
                const osc = actx.createOscillator()
                const gain = actx.createGain()
                osc.type = 'square'
                osc.connect(gain)
                gain.connect(actx.destination)
                osc.frequency.setValueAtTime(800 + Math.random() * 400, actx.currentTime)
                gain.gain.setValueAtTime(0.03, actx.currentTime)
                gain.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + 0.08)
                osc.start(actx.currentTime)
                osc.stop(actx.currentTime + 0.08)
            } catch {}
        }

        const draw = () => {
            if (!running) return
            ctx.clearRect(0, 0, w, h)

            ctx.fillStyle = '#0f0f1a'
            ctx.fillRect(0, 0, w, h)

            ctx.setLineDash([3, 3])
            ctx.strokeStyle = '#2a2a4a'
            ctx.beginPath()
            ctx.moveTo(w / 2, 0)
            ctx.lineTo(w / 2, h)
            ctx.stroke()
            ctx.setLineDash([])

            paddleLeftY += (ballY - paddleLeftY) * 0.15
            ctx.fillStyle = '#4ade80'
            ctx.shadowColor = '#4ade80'
            ctx.shadowBlur = 8
            ctx.fillRect(4, paddleLeftY - 12, 4, 24)

            paddleRightY += (ballY - paddleRightY) * 0.12
            ctx.fillStyle = '#60a5fa'
            ctx.shadowColor = '#60a5fa'
            ctx.shadowBlur = 8
            ctx.fillRect(w - 8, paddleRightY - 12, 4, 24)
            ctx.shadowBlur = 0

            ctx.fillStyle = '#fff'
            ctx.shadowColor = '#4ade80'
            ctx.shadowBlur = 12
            ctx.beginPath()
            ctx.arc(ballX, ballY, 4, 0, Math.PI * 2)
            ctx.fill()
            ctx.shadowBlur = 0

            for (let i = 1; i <= 3; i++) {
                ctx.fillStyle = `rgba(74, 222, 128, ${0.15 - i * 0.04})`
                ctx.beginPath()
                ctx.arc(ballX - dx * i * 2, ballY - dy * i * 2, 3, 0, Math.PI * 2)
                ctx.fill()
            }

            ballX += dx
            ballY += dy

            if (ballY < 5 || ballY > h - 5) dy *= -1

            if (ballX < 12) {
                dx = Math.abs(dx)
                dy = (ballY - paddleLeftY) * 0.15
                playPong()
            }
            if (ballX > w - 12) {
                dx = -Math.abs(dx)
                dy = (ballY - paddleRightY) * 0.15
                playPong()
            }

            requestAnimationFrame(draw)
        }

        const animId = requestAnimationFrame(draw)
        return () => { running = false; cancelAnimationFrame(animId) }
    }, [active, size])

    if (!active) return null

    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <canvas ref={canvasRef} style={{
                width: size * 3, height: size,
                borderRadius: '8px',
            }} />
            <div style={{
                marginTop: '8px', fontSize: '12px', color: '#4ade80',
                fontFamily: 'monospace', letterSpacing: '1px',
                animation: 'pulse 1.5s infinite',
            }}>
                🏓 핑퐁이가 답변을 준비하고 있어요...
            </div>
        </div>
    )
}
