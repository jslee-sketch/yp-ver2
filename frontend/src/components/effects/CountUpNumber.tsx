import { useEffect, useState } from 'react'

export default function CountUpNumber({ value, duration = 1000, prefix = '', suffix = '' }: {
    value: number, duration?: number, prefix?: string, suffix?: string
}) {
    const [display, setDisplay] = useState(0)

    useEffect(() => {
        const start = 0
        const end = value
        const startTime = Date.now()
        let running = true

        const animate = () => {
            if (!running) return
            const elapsed = Date.now() - startTime
            const progress = Math.min(elapsed / duration, 1)
            const eased = 1 - Math.pow(1 - progress, 3)

            setDisplay(Math.floor(start + (end - start) * eased))

            if (progress < 1) requestAnimationFrame(animate)
        }

        requestAnimationFrame(animate)
        return () => { running = false }
    }, [value, duration])

    return <span>{prefix}{display.toLocaleString()}{suffix}</span>
}
