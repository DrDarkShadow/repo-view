import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import { CopyButton } from '../components';

const links = [
  { label: 'Features',   href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Watch Mode', href: '#watch-mode' },
  { label: 'Commands',   href: '#commands' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-brand-dark/90 backdrop-blur border-b border-brand-border'
          : 'bg-transparent'
      }`}
    >
      <div className="container-max">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="#" className="font-mono font-bold text-white text-lg tracking-tight">
            repo<span className="text-brand-accent">view</span>
          </a>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-6">
            {links.map(l => (
              <a
                key={l.href}
                href={l.href}
                className="text-sm text-gray-400 hover:text-white transition-colors duration-200"
              >
                {l.label}
              </a>
            ))}
          </nav>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-3">
            <div className="flex items-center gap-2 bg-gray-950 border border-brand-border rounded-lg px-3 py-1.5">
              <code className="font-mono text-xs text-brand-cyan">pip install repoview</code>
              <CopyButton text="pip install repoview" label="Copy" />
            </div>
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden text-gray-400 hover:text-white"
            onClick={() => setOpen(!open)}
            aria-label="Toggle menu"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile menu */}
        {open && (
          <div className="md:hidden border-t border-brand-border py-4 space-y-3">
            {links.map(l => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block text-sm text-gray-400 hover:text-white transition-colors px-2 py-1"
              >
                {l.label}
              </a>
            ))}
            <div className="pt-2 px-2">
              <div className="flex items-center gap-2 bg-gray-950 border border-brand-border rounded-lg px-3 py-2">
                <code className="font-mono text-xs text-brand-cyan">pip install repoview</code>
                <CopyButton text="pip install repoview" label="Copy" />
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
