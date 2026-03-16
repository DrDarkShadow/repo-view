import { Github, GitBranch, Download } from 'lucide-react';
import { SectionHeading, TerminalWindow } from '../components';

export function GitHubSupport() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="GitHub Integration"
          title="Process Any GitHub Repo Instantly"
          subtitle="Paste a GitHub URL and go — branch selection, download, and processing all automated"
        />

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="flex items-start gap-4 mb-6">
              <Github className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Direct URL Support</h3>
                <p className="text-gray-400">
                  Pass any GitHub repo URL directly to repoview. No need to clone manually — it handles everything.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 mb-6">
              <GitBranch className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Interactive Branch Selection</h3>
                <p className="text-gray-400">
                  Fetches real branch list from GitHub API. Pick the branch you want from an interactive menu, or enter manually if needed.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Download className="text-brand-accent flex-shrink-0 mt-1" size={24} />
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Auto Cleanup</h3>
                <p className="text-gray-400">
                  Downloads as ZIP, extracts to temp folder, processes it, then cleans up automatically. Your workspace stays clean.
                </p>
              </div>
            </div>
          </div>

          <TerminalWindow title="repoview https://github.com/user/repo">
{`Fetching branches from GitHub…

? Select branch:
  ❯ main
    develop
    feature/auth
    v2.0
    [Enter branch name manually]

✔ Downloading main branch…
✔ Extracted to /tmp/repoview_abc123/

Scanning user-repo…

  Files found    247
  Total size     8.3 MB
  Est. tokens    ~45,000

? Skip documentation files? Yes
? Skip test files? Yes

✔ Done in 2.1s

  Output    user-repo-context.txt
  Tokens    43,200 / 80,000`}
          </TerminalWindow>
        </div>
      </div>
    </section>
  );
}
