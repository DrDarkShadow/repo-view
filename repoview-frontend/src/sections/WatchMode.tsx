import { Eye } from 'lucide-react';
import { SectionHeading, TerminalWindow } from '../components';

export function WatchMode() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="Live Updates"
          title="Watch Mode: Keep Your Context Fresh"
          subtitle="Your context file updates automatically as you code"
        />

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="flex items-start gap-4 mb-6">
              <Eye className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Real-time Sync</h3>
                <p className="text-gray-400">
                  Every time you save a file in your editor, repoview detects the change and updates your context file automatically.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 mb-6">
              <Zap className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Lightning Fast</h3>
                <p className="text-gray-400">
                  Updates complete in 0.1–1 second. Debounced to handle rapid saves like git checkout or npm install.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="text-brand-accent flex-shrink-0 mt-1 text-lg font-bold">◆</div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Always in Sync</h3>
                <p className="text-gray-400">
                  Never paste stale context again. Your AI assistant always has the latest version of your code.
                </p>
              </div>
            </div>
          </div>

          <TerminalWindow title="repoview --watch">
{`[12:34:56] Watching my-project for changes…

[12:35:02] ✔ src/App.tsx modified
           Updated in 0.3s

[12:35:15] ✔ package.json modified
           Updated in 0.2s

[12:35:23] ✔ src/utils.ts created
           Updated in 0.4s

[12:35:45] ✔ components/Button.tsx modified
           Updated in 0.2s

Context file is always up-to-date.
Ready to paste into your AI assistant.`}
          </TerminalWindow>
        </div>
      </div>
    </section>
  );
}

function Zap({ className, size }: { className: string; size: number }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
    </svg>
  );
}
