

export default function RequireAuth({
  children,
}: {
  children: React.ReactNode;
}) {
  // Authentication removed: always render children
  return <>{children}</>;
}
