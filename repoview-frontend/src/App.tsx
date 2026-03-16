import {
  Hero,
  Problem,
  HowItWorks,
  Features,
  WatchMode,
  Commands,
  ForWho,
  QuickStart,
  Footer,
} from './sections';

function App() {
  return (
    <div className="min-h-screen bg-brand-dark text-gray-100">
      <Hero />
      <Problem />
      <HowItWorks />
      <Features />
      <WatchMode />
      <Commands />
      <ForWho />
      <QuickStart />
      <Footer />
    </div>
  );
}

export default App;
