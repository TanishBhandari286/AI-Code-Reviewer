import React from 'react'
import styles from './Card.module.css'

export function Card({ children, className = '', ...props }) {
  return (
    <div className={[styles.card, className].join(' ')} {...props}>
      {children}
    </div>
  )
}

export function CardPanel({ children, className = '', ...props }) {
  return (
    <div className={[styles.card, styles.panel, className].join(' ')} {...props}>
      {children}
    </div>
  )
}

export function CardItem({ children, className = '', ...props }) {
  return (
    <div className={[styles.card, styles.item, className].join(' ')} {...props}>
      {children}
    </div>
  )
}
