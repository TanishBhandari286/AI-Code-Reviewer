import React from 'react'
import styles from './Button.module.css'

export default function Button({ children, variant = 'default', cta = false, className = '', ...props }) {
  const classes = [styles.root]
  if (variant === 'primary') classes.push(styles.primary)
  if (cta) classes.push(styles.cta)
  if (className) classes.push(className)
  return (
    <button className={classes.join(' ')} {...props}>
      {children}
    </button>
  )
}
