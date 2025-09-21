import React, { useEffect, useRef } from 'react'

export default function BackgroundAnimation() {
  const canvasRef = useRef(null)
  const rafRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')

    let dpi = Math.max(1, window.devicePixelRatio || 1)
    let w = 0, h = 0

    function resize() {
      w = canvas.clientWidth
      h = canvas.clientHeight
      canvas.width = Math.floor(w * dpi)
      canvas.height = Math.floor(h * dpi)
      ctx.setTransform(dpi, 0, 0, dpi, 0, 0)
    }

    const particles = Array.from({ length: 36 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: 1.2 + Math.random() * 1.8
    }))

    function step() {
      ctx.clearRect(0, 0, w, h)
      // draw links
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]
        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j]
          const dx = p.x - q.x
          const dy = p.y - q.y
          const dist = Math.hypot(dx, dy)
          if (dist < 120) {
            const alpha = (1 - dist / 120) * 0.35
            ctx.strokeStyle = `rgba(0,194,255,${alpha})`
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(q.x, q.y)
            ctx.stroke()
          }
        }
      }
      // draw particles
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        if (p.x < -20) p.x = w + 20
        if (p.x > w + 20) p.x = -20
        if (p.y < -20) p.y = h + 20
        if (p.y > h + 20) p.y = -20

        const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 16)
        grd.addColorStop(0, 'rgba(124,58,237,0.55)')
        grd.addColorStop(1, 'rgba(124,58,237,0)')
        ctx.fillStyle = grd
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r * 5, 0, Math.PI * 2)
        ctx.fill()

        ctx.fillStyle = 'rgba(0,194,255,0.9)'
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      }
      rafRef.current = requestAnimationFrame(step)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    resize()
    step()
    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
    }
  }, [])

  return (
    <div className="bg-anim" aria-hidden="true">
      <canvas ref={canvasRef} className="bg-anim-canvas" />
    </div>
  )
}
