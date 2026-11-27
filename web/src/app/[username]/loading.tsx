export default function UserDashboardLoading() {
  return (
    <main className="mx-auto max-w-6xl animate-pulse space-y-6 px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="h-8 w-52 rounded-lg bg-slate-200 dark:bg-slate-800" />
          <div className="h-4 w-72 rounded bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="h-10 w-36 rounded-xl bg-slate-200 dark:bg-slate-800" />
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-24 rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
          />
        ))}
      </div>

      <div className="h-80 rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900" />
    </main>
  );
}
