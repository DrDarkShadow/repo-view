import {
  Sparkles,
  Clock,
  Eye,
  Zap,
  Shield,
  RotateCcw,
  Github,
  FileArchive,
} from 'lucide-react';
import { SectionHeading, FeatureCard } from '../components';

const features = [
  {
    icon: Sparkles,
    title: 'Interactive Wizard',
    description: 'Vite-style interactive prompts. Asks only relevant questions — if no test files exist, it skips that question.',
  },
  {
    icon: Clock,
    title: 'Smart Diff & Cache',
    description: 'Remembers your project between runs. Next time, only changed files are processed. Milliseconds, not seconds.',
  },
  {
    icon: Eye,
    title: 'Watch Mode',
    description: 'Live file watching with --watch flag. Every save updates your context file instantly. Always current.',
  },
  {
    icon: Zap,
    title: 'Token Trimming',
    description: 'Essential files prioritized. When token budgets are exceeded, less-critical files are intelligently summarized.',
  },
  {
    icon: Shield,
    title: 'Zero Project Pollution',
    description: 'Cache stored in ~/.repoview/cache/. Your project folder stays pristine. No hidden files or configs.',
  },
  {
    icon: RotateCcw,
    title: 'Reset Flag',
    description: 'Wrong settings? Run --reset to clear the cache and launch the wizard fresh with one command.',
  },
  {
    icon: Github,
    title: 'GitHub URL Support',
    description: 'Pass a GitHub repo URL directly. Fetches branches, lets you pick one, downloads and processes it automatically.',
  },
  {
    icon: FileArchive,
    title: 'ZIP File Support',
    description: 'Point at a .zip file and repoview extracts it temporarily, processes it like a normal folder, then cleans up.',
  },
];

export function Features() {
  return (
    <section className="py-20 bg-brand-dark">
      <div className="container-max">
        <SectionHeading
          eyebrow="Core Features"
          title="Everything you need to prepare context"
          subtitle="Smart, fast, and designed for developers"
        />

        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <FeatureCard key={idx} {...feature} />
          ))}
        </div>
      </div>
    </section>
  );
}
