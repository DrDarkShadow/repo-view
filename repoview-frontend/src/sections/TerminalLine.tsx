/**
 * TerminalLine — render a single terminal output line with colour tokens.
 * 
 * Usage:
 *   <TerminalLine type="success">✔ Done in 3.8s</TerminalLine>
 *   <TerminalLine type="prompt">◆ Skip docs? › Yes</TerminalLine>
 *   <TerminalLine type="dim">Scanning my-project…</TerminalLine>
 */

type LineType =
  | 'default'
  | 'success'   // green ✔
  | 'error'     // red ✗
  | 'warning'   // yellow ⚠
  | 'prompt'    // purple ◆
  | 'dim'       // gray
  | 'cyan'      // cyan — file names, tokens
  | 'accent'    // purple — menu pointer ❯
  | 'timestamp' // dim gray timestamp prefix
  | 'blank';

interface TerminalLineProps {
  type?: LineType;
  children: React.ReactNode;
}

const colorMap: Record<LineType, string> = {
  default:   'text-gray-200',
  success:   'text-emerald-400',
  error:     'text-red-400',
  warning:   'text-yellow-400',
  prompt:    'text-brand-accent',
  dim:       'text-gray-500',
  cyan:      'text-brand-cyan',
  accent:    'text-brand-accent font-semibold',
  timestamp: 'text-gray-600',
  blank:     '',
};

export function TerminalLine({ type = 'default', children }: TerminalLineProps) {
  if (type === 'blank') return <div className="h-2" />;
  return (
    <div className={`font-mono text-sm leading-relaxed ${colorMap[type]}`}>
      {children}
    </div>
  );
}
