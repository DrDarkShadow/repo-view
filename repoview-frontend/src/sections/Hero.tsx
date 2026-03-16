import { Github, Terminal } from 'lucide-react';
import { CopyButton } from '../components';
import { TerminalWindow } from '../components';

export function Hero() {
  const installCommand = 'pip install repoview';

  return (
    <section className="min-h-screen bg-brand-dark flex items-center justify-center py-20">
      <div className="container-max w-full">
        <div className="max-w-4xl mx-auto">
          {/* Main headline */}
          <div className="mb-8 text-center">
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight text-white">
              Your entire codebase.{' '}
              <span className="gradient-text">One paste.</span>{' '}
              Any AI.
            </h1>
            <p className="text-lg sm:text-xl text-gray-400 mb-8 leading-relaxed max-w-2xl mx-auto">
              repoview turns any project into LLM-ready context in seconds — with a single command. Paste your entire codebase into Claude, ChatGPT, Gemini, or any AI assistant.
            </p>
          </div>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <div className="flex items-center gap-3 bg-gray-950 border border-brand-border rounded-lg px-4 py-2">
              <code className="font-mono text-sm text-brand-cyan">{installCommand}</code>
              <CopyButton text={installCommand} label="Copy" />
            </div>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary-outline gap-2"
            >
              <Github size={18} />
              View on GitHub
            </a>
          </div>

          {/* Terminal demo */}
          <div className="mb-8 animate-slide-up">
            <TerminalWindow title="repoview">
{`╭──────────────────────────────────────────────────────╮
│  repoview  v1.0.0                                   │
│  Turn any codebase into LLM-ready context           │
╰──────────────────────────────────────────────────────╯

  Scanning my-project…

  Files found      147
  Total size       3.1 MB
  Est. tokens      ~218,000
  Top types        .ts 43  .tsx 28  .json 19

◆  Skip documentation files?  › Yes
◆  Skip test files?  › Yes
◆  Respect .gitignore?  › Yes
◆  Output file name:  my-project-context.txt

  ████████████████████████  Processing 147 files…

✔  Done in 3.8s

  Tokens   ████████░░░░  142,847 / 800,000  (18%)
  Full      98 files
  Summarised 12 files
  Skipped   37 files

❯  📋 Copy text to clipboard
   📄 Copy file to clipboard
   📁 Open output folder
   🔁 Run again
   ❌ Exit`}
            </TerminalWindow>
          </div>

          {/* Scroll indicator */}
          <div className="flex justify-center">
            <div className="animate-bounce">
              <Terminal size={20} className="text-brand-accent" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
