const Header = () => (
  <header className="flex items-start justify-between px-6 py-5">
    <div>
      <h1 className="text-2xl font-bold tracking-tight">TTC Map</h1>
      <p className="mt-1 text-sm text-slate-400">Toronto&apos;s subway, live</p>
    </div>

    <a
      href="/search/"
      className="glow-orange rounded-lg bg-orange-500 px-5 py-2.5 text-sm font-semibold text-white transition-shadow"
    >
      TTC LIVE SEARCH
    </a>
  </header>
);

export default Header;
