import { CopyButton } from './CopyButton';

interface CommandBlockProps {
  command: string;
  showCopy?: boolean;
  children?: React.ReactNode;
}

export function CommandBlock({ command, showCopy = true, children }: CommandBlockProps) {
  return (
    <div className="bg-gray-950 border border-brand-border rounded-lg p-4 overflow-x-auto">
      <div className="flex items-center justify-between gap-4 mb-2">
        <code className="font-mono text-sm text-brand-cyan whitespace-nowrap">
          {command}
        </code>
        {showCopy && <CopyButton text={command} label="Copy" />}
      </div>
      {children && <div className="text-xs text-gray-500 mt-2">{children}</div>}
    </div>
  );
}
