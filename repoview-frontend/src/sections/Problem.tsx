import { AlertCircle } from 'lucide-react';
import { SectionHeading } from '../components';
import { useScrollReveal } from '../hooks';

export function Problem() {
  const { ref, isVisible } = useScrollReveal();

  return (
    <section className="py-20 bg-brand-dark" ref={ref}>
      <div className="container-max">
        <div className={`max-w-3xl mx-auto transition-all duration-700 ${isVisible ? 'opacity-100' : 'opacity-0'}`}>
          <div className="flex gap-6 items-start">
            <div className="flex-shrink-0 mt-1">
              <AlertCircle className="text-brand-accent" size={28} />
            </div>
            <div>
              <SectionHeading
                eyebrow="The Problem"
                title="Copying files one by one is broken"
                centered={false}
              />
              <p className="text-gray-400 text-lg leading-relaxed mt-6">
                When you ask an AI assistant for help with your codebase, you have to manually copy-paste files one by one. Or describe your folder structure from scratch. You hit context limits. You forget critical files. You spend more time prepping the context than asking the question.
              </p>
              <p className="text-gray-400 text-lg leading-relaxed mt-4">
                repoview fixes this. One command. Your entire codebase becomes a clean, structured, AI-ready context file. Paste it, ask your question, get answers that actually understand your full project.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
