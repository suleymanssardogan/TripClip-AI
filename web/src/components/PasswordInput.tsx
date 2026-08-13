"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

interface Props {
  id?: string;
  name?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  className?: string;
  autoComplete?: string;
}

/**
 * Şifre input'u — sağ tarafta göster/gizle butonu (göz ikonu).
 * `name` ile form-data desteği var (login/signup'ta uncontrolled kullanım).
 */
export default function PasswordInput({
  id,
  name = "password",
  placeholder = "••••••••",
  required = false,
  disabled = false,
  value,
  onChange,
  className = "",
  autoComplete = "current-password",
}: Props) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        id={id}
        name={name}
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        className={`w-full bg-surface2 border border-border-strong rounded-md px-4 py-3.5 pr-11
          text-text placeholder:text-text-tertiary text-sm
          focus:outline-none focus:border-accent-text transition-colors ${className}`}
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        tabIndex={-1}
        aria-label={visible ? "Şifreyi gizle" : "Şifreyi göster"}
        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-sm
          text-text-tertiary hover:text-text transition-colors disabled:opacity-50"
        disabled={disabled}
      >
        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}
