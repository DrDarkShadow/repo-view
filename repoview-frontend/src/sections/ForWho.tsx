import { Users, Code2, Bug, GitBranch } from 'lucide-react';
import { SectionHeading } from '../components';

const audiences = [
  {
    icon: Users,
    title: 'Daily AI Users',
    description: 'Developers working with Claude, ChatGPT, and Gemini daily. Save hours of context prep per week.',
  },
  {
    icon: Code2,
    title: 'Code Reviewers',
    description: 'Teams doing code reviews with LLMs. Share full context instantly with consistent formatting.',
  },
  {
    icon: Bug,
    title: 'Debuggers',
    description: 'Debugging complex multi-file issues? Give the AI your entire codebase context in one paste.',
  },
  {
    icon: GitBranch,
    title: 'OSS Contributors',
    description: 'Understanding a large open-source project? Let repoview help the AI understand it too.',
  },
];

export function ForWho() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="Who Is This For"
          title="Built for modern developers"
          subtitle="Anyone who codes with AI knows the pain"
        />

        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-6">
          {audiences.map((item, idx) => (
            <div key={idx} className="card p-6 border-brand-border">
              <div className="flex items-start gap-4">
                <item.icon className="text-brand-accent flex-shrink-0 mt-1" size={24} />
                <div>
                  <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{item.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
