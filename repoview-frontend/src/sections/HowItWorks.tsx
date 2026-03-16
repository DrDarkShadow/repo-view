import { Download, Terminal, Zap } from 'lucide-react';
import { SectionHeading, StepCard } from '../components';
import { useScrollReveal } from '../hooks';

export function HowItWorks() {
  const { ref, isVisible } = useScrollReveal();

  return (
    <section className="py-20 bg-brand-dark" ref={ref}>
      <div className="container-max">
        <SectionHeading
          eyebrow="How It Works"
          title="Three steps to AI-ready context"
          subtitle="From codebase to LLM conversation in seconds"
        />

        <div className={`mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12 transition-all duration-700 ${isVisible ? 'opacity-100' : 'opacity-0'}`}>
          <StepCard
            number={1}
            icon={Download}
            title="Install"
            description="Run pip install repoview once. That's it. Works with any Python version."
          />
          <StepCard
            number={2}
            icon={Terminal}
            title="Run in Your Project"
            description="Type repoview in any folder. Answer a few smart questions. Watch it scan your codebase."
          />
          <StepCard
            number={3}
            icon={Zap}
            title="Paste into AI"
            description="Copy the output file and paste directly into Claude, ChatGPT, Gemini — any AI assistant."
          />
        </div>
      </div>
    </section>
  );
}
