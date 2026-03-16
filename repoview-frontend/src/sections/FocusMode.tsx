import { Target, FileText, FolderTree } from 'lucide-react';
import { SectionHeading, TerminalWindow } from '../components';

export function FocusMode() {
  return (
    <section className="py-20 bg-brand-card">
      <div className="container-max">
        <SectionHeading
          eyebrow="Precision Context"
          title="Focus Mode: Zero In on What Matters"
          subtitle="Get full content for a specific folder or file — everything else stays as structure only"
        />

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="flex items-start gap-4 mb-6">
              <Target className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Laser-Focused Context</h3>
                <p className="text-gray-400">
                  Point repoview at a subfolder or single file. That path gets full content — the rest of the repo appears as a file tree only, keeping tokens low.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 mb-6">
              <FolderTree className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Repo Structure Preserved</h3>
                <p className="text-gray-400">
                  Your AI still sees the full project layout, so it understands how your focused code fits into the bigger picture.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <FileText className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Works with Watch Mode</h3>
                <p className="text-gray-400">
                  Combine <code className="text-brand-accent">--focus</code> with <code className="text-brand-accent">--watch</code> to get live-updating, laser-focused context as you work on a feature.
                </p>
              </div>
            </div>
          </div>

          <TerminalWindow title="repoview --focus src/auth">
{`⚡  Focus mode
    folder: src/auth
    All other files → tree only, no content.

✔ Done in 0.8s

  Output      my-project-src-auth-context.txt
  Tokens      ████████░░░░░░░░░░░░░░░░  12,400 / 80,000
  Focused     8 files  (full content)
  Tree only   143 files

Tip: Combine with --watch for live updates:
  repoview --focus src/auth --watch`}
          </TerminalWindow>
        </div>
      </div>
    </section>
  );
}
