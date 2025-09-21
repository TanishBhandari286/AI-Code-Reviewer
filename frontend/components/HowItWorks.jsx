import React from 'react'

const steps = [
  { n: 1, title: 'Submit Repo URL', desc: 'Paste your GitHub repository link into the form.' },
  { n: 2, title: 'AI Analyzes Code', desc: 'We classify files and craft targeted feedback.' },
  { n: 3, title: 'PR Generated Automatically', desc: 'A branch is created and a PR is opened for you.' },
  { n: 4, title: 'Receive Feedback & Improve', desc: 'Review comments, iterate, and merge confidently.' },
]

export default function HowItWorks() {
  return (
    <section className="how">
      <h2 className="how-title">How it works</h2>
      <div className="how-grid">
        {steps.map((s) => (
          <div key={s.n} className="how-step">
            <div className="how-badge">{s.n}</div>
            <div className="how-body">
              <div className="how-step-title">{s.title}</div>
              <div className="how-step-desc">{s.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
