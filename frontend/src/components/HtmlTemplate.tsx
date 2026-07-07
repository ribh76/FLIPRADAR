import { useEffect, useRef } from "react";

type HtmlTemplateProps = {
  html: string;
  onMount?: (root: HTMLDivElement) => void | (() => void);
};

export function HtmlTemplate({ html, onMount }: HtmlTemplateProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!rootRef.current || !onMount) {
      return;
    }
    return onMount(rootRef.current);
  }, [html, onMount]);

  return <div ref={rootRef} dangerouslySetInnerHTML={{ __html: html }} />;
}
