import { Video as LucideIcon } from 'lucide-react';

interface StepCardProps {
  number: number;
  icon: LucideIcon;
  title: string;
  description: string;
}

export function StepCard({ number, icon: Icon, title, description }: StepCardProps) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="mb-4 relative">
        <div className="w-16 h-16 rounded-full bg-brand-accent bg-opacity-10 border-2 border-brand-accent flex items-center justify-center">
          <Icon size={28} className="text-brand-accent" />
        </div>
        <div className="absolute -top-2 -left-2 w-6 h-6 bg-brand-accent text-brand-dark rounded-full flex items-center justify-center text-sm font-bold">
          {number}
        </div>
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-gray-400 text-sm leading-relaxed max-w-xs">{description}</p>
    </div>
  );
}
