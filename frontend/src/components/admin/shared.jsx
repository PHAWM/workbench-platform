import React from 'react';

// Shared, modern UI primitives for the admin setup pages.
// Keeps the existing purple brand palette; refines spacing, hierarchy and focus states.

// A labelled field wrapper: label + control + optional helper/error text as one unit.
export const Field = ({ label, required, htmlFor, helper, error, className = '', children }) => (
  <div className={className}>
    {label && (
      <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
        {required && <span className="text-purple-600 ml-0.5">*</span>}
      </label>
    )}
    {children}
    {error ? (
      <p className="text-xs text-red-600 mt-1">{error}</p>
    ) : helper ? (
      <p className="text-xs text-gray-400 mt-1">{helper}</p>
    ) : null}
  </div>
);

// Consistent control styling shared by inputs, textareas and selects.
export const controlClass =
  'w-full px-3.5 py-2.5 bg-white border-2 border-purple-100 rounded-xl text-gray-800 ' +
  'placeholder:text-gray-400 outline-none transition-colors ' +
  'focus:border-purple-400 focus:ring-2 focus:ring-purple-100 ' +
  'disabled:bg-gray-50 disabled:text-gray-400';

export const TextInput = ({ className = '', ...props }) => (
  <input className={`${controlClass} ${className}`} {...props} />
);

export const TextArea = ({ className = '', rows = 3, ...props }) => (
  <textarea rows={rows} className={`${controlClass} ${className}`} {...props} />
);

export const Select = ({ className = '', children, ...props }) => (
  <select className={`${controlClass} ${className}`} {...props}>
    {children}
  </select>
);

// Buttons — a real primary/secondary hierarchy (previously both looked identical).
export const PrimaryButton = ({ className = '', children, ...props }) => (
  <button
    className={`inline-flex items-center gap-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 ` +
      `px-5 py-2.5 rounded-full text-sm font-semibold border-2 border-purple-200 transition-colors ` +
      `disabled:bg-gray-100 disabled:text-gray-400 disabled:border-gray-200 disabled:cursor-not-allowed ${className}`}
    {...props}
  >
    {children}
  </button>
);

export const SecondaryButton = ({ className = '', children, ...props }) => (
  <button
    className={`inline-flex items-center gap-1.5 bg-white hover:bg-purple-50 text-purple-700 ` +
      `px-5 py-2.5 rounded-full text-sm font-semibold border-2 border-purple-200 transition-colors ` +
      `disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    {...props}
  >
    {children}
  </button>
);

// A page shell: title, optional description, then the page body, then a footer
// action row (Back / Next). Gives every admin page a consistent modern frame.
export const PageShell = ({ title, description, children, footer }) => (
  <div className="flex flex-col h-full">
    <div className="mb-6">
      <h3 className="text-xl font-semibold text-gray-900">{title}</h3>
      {description && <p className="text-sm text-gray-500 mt-1">{description}</p>}
    </div>
    <div className="flex-1 space-y-5">{children}</div>
    {footer && <div className="flex items-center justify-between pt-6 mt-6 border-t border-gray-100">{footer}</div>}
  </div>
);

// A soft card for grouping created items (events/entities/metrics lists, pickers, etc.).
export const Card = ({ className = '', children }) => (
  <div className={`border-2 border-purple-100 rounded-2xl p-4 bg-white ${className}`}>{children}</div>
);
