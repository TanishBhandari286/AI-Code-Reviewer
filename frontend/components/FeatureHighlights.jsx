import React from 'react'

const features = [
  { icon: '🧠', title: 'Smart Code Analysis', desc: 'Topic-aware feedback tailored to DS&A, algorithms, and patterns.' },
  { icon: '🤖', title: 'Automated PR Creation', desc: 'Branches, commits, and PRs generated for your review flow.' },
  { icon: '🛡️', title: 'Security Best Practices', desc: 'Guidance on safe coding, input validation, and invariants.' },
  { icon: '🧩', title: 'DSA Interview Mode', desc: 'Hints and questions aligned with common interview drills.' },
]

export default function FeatureHighlights() {
  return (
    <section className="features">
      <div className="features-grid">
        {features.map((f, i) => (
          <div key={i} className="feature-card">
            <div className="feature-icon" aria-hidden>{f.icon}</div>
            <h3 className="feature-title">{f.title}</h3>
            <p className="feature-desc">{f.desc}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
