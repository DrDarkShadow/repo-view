interface TerminalWindowProps {
  title?: string;
  children: React.ReactNode;
}

export function TerminalWindow({ title = 'repoview', children }: TerminalWindowProps) {
  return (
    <div className="terminal-window">
      <div className="terminal-header">
        <div className="terminal-dot terminal-dot-red"></div>
        <div className="terminal-dot terminal-dot-yellow"></div>
        <div className="terminal-dot terminal-dot-green"></div>
        <span className="ml-3 text-xs text-gray-500">{title}</span>
      </div>
      <div className="terminal-content">
        {children}
      </div>
    </div>
  );
}
