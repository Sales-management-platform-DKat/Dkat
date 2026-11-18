import React from 'react';

const buttonVariants = {
  primary: 'primary',
  secondary: 'secondary',
  outline: 'outline',
  ghost: 'ghost',
  destructive: 'danger',
  success: 'success',
  icon: 'icon-btn',
  floating: 'fab',
};

export function Button({
  as,
  variant = 'primary',
  size,
  loading = false,
  disabled = false,
  className = '',
  children,
  type,
  href,
  ...props
}) {
  const Element = as || (href ? 'a' : 'button');
  const classes = [
    variant === 'icon' || variant === 'floating' ? '' : 'btn',
    buttonVariants[variant] || buttonVariants.primary,
    size,
    className,
  ].filter(Boolean).join(' ');

  return (
    <Element
      {...props}
      {...(href ? { href } : {})}
      className={classes}
      type={Element === 'button' ? (type || 'button') : undefined}
      disabled={Element === 'button' ? disabled || loading : undefined}
      aria-busy={loading || undefined}
    >
      {loading && <span className="btn-spinner" aria-hidden="true" />}
      {children}
    </Element>
  );
}

export function Select({ children, className = '', ...props }) {
  return (
    <span className={`select-control${className ? ` ${className}` : ''}`}>
      <select {...props}>{children}</select>
      <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <path d="m5.5 7.5 4.5 4.5 4.5-4.5" />
      </svg>
    </span>
  );
}

export function Checkbox({ label, description, className = '', ...props }) {
  return (
    <label className={`check-control${className ? ` ${className}` : ''}`}>
      <input type="checkbox" {...props} />
      <span>
        <b>{label}</b>
        {description && <small>{description}</small>}
      </span>
    </label>
  );
}

export function ToggleSwitch({ label, className = '', ...props }) {
  return (
    <label className={`toggle-control${className ? ` ${className}` : ''}`}>
      <span>{label}</span>
      <span className="toggle-switch">
        <input type="checkbox" role="switch" {...props} />
        <span aria-hidden="true" />
      </span>
    </label>
  );
}

export function SegmentedControl({ label, options, value, onChange, className = '' }) {
  return (
    <div className={`segmented-control${className ? ` ${className}` : ''}`} role="group" aria-label={label}>
      {options.map((option) => {
        const item = typeof option === 'string' ? { value: option, label: option } : option;
        const selected = item.value === value;
        return (
          <button key={item.value} type="button" aria-pressed={selected} onClick={() => onChange(item.value)}>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
