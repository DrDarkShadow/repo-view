import { Terminal } from 'lucide-react';
import { SectionHeading, CommandBlock } from '../components';

export function QuickStart() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="Get Started"
          title="Three commands. That's all."
          subtitle="From zero to context in 30 seconds"
        />

        <div className="mt-16 max-w-2xl mx-auto space-y-4">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-accent bg-opacity-10 border border-brand-accent flex items-center justify-center">
              <span className="text-brand-accent font-bold text-sm">1</span>
            </div>
            <div className="flex-grow">
              <p className="text-gray-400 text-sm mb-2">Install repoview</p>
              <CommandBlock command="pip install repoview" />
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-accent bg-opacity-10 border border-brand-accent flex items-center justify-center">
              <span className="text-brand-accent font-bold text-sm">2</span>
            </div>
            <div className="flex-grow">
              <p className="text-gray-400 text-sm mb-2">Navigate to your project</p>
              <CommandBlock command="cd your-project" />
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-accent bg-opacity-10 border border-brand-accent flex items-center justify-center">
              <span className="text-brand-accent font-bold text-sm">3</span>
            </div>
            <div className="flex-grow">
              <p className="text-gray-400 text-sm mb-2">Run repoview</p>
              <CommandBlock command="repoview" />
            </div>
          </div>
        </div>

        <div className="mt-12 text-center">
          <p className="text-gray-400 mb-4">Answer a few questions, copy the output, paste into your AI assistant.</p>
          <p className="text-sm text-gray-500">That's it. No configuration. No setup.</p>
        </div>
      </div>
    </section>
  );
}
