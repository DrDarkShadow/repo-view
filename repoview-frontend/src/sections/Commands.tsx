import { SectionHeading, CommandBlock } from '../components';

const commands = [
  { cmd: 'repoview', desc: 'Launch interactive wizard in current directory' },
  { cmd: 'rv ./my-project', desc: 'Short alias — same as repoview' },
  { cmd: 'repoview --quick ./my-project', desc: 'No questions asked, instant run with defaults' },
  { cmd: 'repoview --focus src/auth', desc: 'Full content for src/auth only, rest is tree structure' },
  { cmd: 'repoview --watch ./my-project', desc: 'Live watch mode, auto-update on file changes' },
  { cmd: 'repoview --copy --quick ./my-project', desc: 'Generate and auto-copy output to clipboard' },
  { cmd: 'repoview --info ./my-project', desc: 'Deep project inspection — no generation, just stats' },
  { cmd: 'repoview project.zip', desc: 'Process a ZIP file directly' },
  { cmd: 'repoview https://github.com/user/repo', desc: 'Clone and process a GitHub repo (branch selection included)' },
  { cmd: 'repoview --reset ./my-project', desc: 'Clear cache and run fresh wizard' },
];

export function Commands() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="CLI Reference"
          title="Commands & Flags"
          subtitle="All the tools you need, right from your terminal"
        />

        <div className="mt-16 max-w-3xl mx-auto space-y-4">
          {commands.map((item, idx) => (
            <div key={idx} className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
              <CommandBlock command={item.cmd} showCopy={true} />
              <p className="text-gray-400 text-sm leading-relaxed md:pt-2">
                {item.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
