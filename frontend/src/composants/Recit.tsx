import styles from "./Recit.module.css";

/**
 * Récit en HTML. Ce HTML est produit ET nettoyé par le serveur
 * (voyages/markdown.py : markdown-it sans HTML brut, puis liste blanche nh3) :
 * c'est pour cela qu'on peut l'insérer tel quel. Ne jamais passer ici un HTML
 * qui ne vient pas de `*_html` de l'API.
 */
export default function Recit({ html, className }: { html: string; className?: string }) {
  if (!html.trim()) return null;
  return (
    <div
      className={[styles.recit, className].filter(Boolean).join(" ")}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
