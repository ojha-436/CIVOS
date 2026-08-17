'use client';

/* The theme control, shared by the landing page, the console masthead and the
 * citizen intake header — so the affordance is in the same visual language and
 * the same place on every surface.
 *
 * Holds no React state. The blocking script in app/layout.tsx may already have
 * set data-theme before hydration, so any useState default would disagree with
 * the real theme for one frame and flip the icon. Both glyphs ship in the markup
 * and CSS picks between them on the attribute, which cannot get out of sync.
 */

import { toggleTheme } from '@/lib/theme';

export default function ThemeToggle({ className = '' }: { className?: string }) {
  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={() => toggleTheme()}
      /* Static label: the button's meaning ("change the theme") does not change
         even though its icon does, and a label that flips on click gets
         announced twice by a screen reader for one action. */
      aria-label="Switch between light and dark theme"
      title="Switch between light and dark theme"
    >
      <span className="t-sun" aria-hidden="true">
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.2v2.4M12 19.4v2.4M2.2 12h2.4M19.4 12h2.4M5.1 5.1l1.7 1.7M17.2 17.2l1.7 1.7M18.9 5.1l-1.7 1.7M6.8 17.2l-1.7 1.7" />
        </svg>
      </span>
      <span className="t-moon" aria-hidden="true">
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a6.9 6.9 0 0 0 11.1 11.1z" />
        </svg>
      </span>
    </button>
  );
}
