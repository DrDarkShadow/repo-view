import { Github } from 'lucide-react';
import { CopyButton } from '../components';

export function Footer() {
  const installCommand = 'pip install repoview';

  return (
    <footer className="border-t border-brand-border bg-brand-dark">
      <div className="container-max py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Brand */}
          <div>
            <h3 className="text-lg font-bold text-white mb-2">repoview</h3>
            <p className="text-gray-400 text-sm">
              Turn any codebase into LLM-ready context. Zero friction between your code and AI.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-4 uppercase tracking-wider">Links</h4>
            <ul className="space-y-2">
              <li>
                <a
                  href="https://github.com/drdarkshadow/repo-view"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-brand-accent text-sm transition-colors"
                >
                  GitHub Repository
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-brand-accent text-sm transition-colors"
                >
                  Report Issues
                </a>
              </li>
              <li>
                <a
                  href="https://pypi.org/project/repoview"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-brand-accent text-sm transition-colors"
                >
                  PyPI Package
                </a>
              </li>
            </ul>
          </div>

          {/* Install */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-4 uppercase tracking-wider">Install</h4>
            <div className="flex items-center gap-2 bg-gray-950 border border-brand-border rounded-lg px-3 py-2">
              <code className="font-mono text-xs text-brand-cyan flex-grow">{installCommand}</code>
              <CopyButton text={installCommand} label="Copy" />
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-brand-border pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-gray-500 text-sm">
            repoview is free and open source. MIT License.
          </p>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-brand-accent transition-colors"
          >
            <Github size={20} />
          </a>
        </div>
      </div>
    </footer>
  );
}
