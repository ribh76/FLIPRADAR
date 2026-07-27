export function Skeleton({
  className = "",
  lines = 1,
}: {
  className?: string;
  lines?: number;
}) {
  if (lines > 1) {
    return (
      <div className={`space-y-2 ${className}`} aria-hidden="true">
        {Array.from({ length: lines }).map((_, index) => (
          <div
            className="h-4 animate-pulse rounded-md bg-[var(--color-border-soft)]"
            key={index}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`animate-pulse rounded-md bg-[var(--color-border-soft)] ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="page-card space-y-4" aria-label="Loading content">
      <Skeleton className="h-5 w-1/3" />
      <Skeleton lines={3} />
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    </div>
  );
}
