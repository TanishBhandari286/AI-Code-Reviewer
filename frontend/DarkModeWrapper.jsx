import React from 'react'

export default function DarkModeWrapper({ children }) {
  // Could be extended later to support light theme toggle.
  return (
    <div className="theme-dark">
      {children}
    </div>
  )
}
