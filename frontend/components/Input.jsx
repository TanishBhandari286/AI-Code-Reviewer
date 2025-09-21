import React from 'react'
import styles from './Input.module.css'

export default function Input({ value, onChange, placeholder, className = '', ...props }) {
  return (
    <div className={[styles.wrap, className].join(' ')}>
      <input className={styles.input} value={value} onChange={onChange} placeholder={placeholder} {...props} />
    </div>
  )
}
