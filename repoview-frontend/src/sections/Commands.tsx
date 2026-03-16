import { SectionHeading, CommandBlock } from '../components';

const commands = [
  { cmd: 'repoview', desc: 'Launch interactive wizard in current directory' },
  { cmd: 'repoview ./my-project', desc: 'Wizard with path pre-filled' },
  { cmd: 'repoview --quick ./my-project', desc: 'No questions asked, instant run with defaults' },
  { cmd: 'repoview --watch ./my-project', desc: 'Live watch mode, auto-update on file changes' },
  { cmd: 'repoview --reset ./my-project', desc: 'Clear cache and run fresh wizard' },
  { cmd: 'repoview --version', desc: 'Show current repoview version' },
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
