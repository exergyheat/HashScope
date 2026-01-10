import { useEffect } from 'react';

export function DocsPage() {
  useEffect(() => {
    // Redirect to the MkDocs static site
    window.location.href = '/docs/';
  }, []);

  return (
    <div className="h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Redirecting to documentation...</h1>
        <p className="text-muted-foreground">
          If you are not redirected, <a href="/docs/" className="text-primary hover:underline">click here</a>.
        </p>
      </div>
    </div>
  );
}
