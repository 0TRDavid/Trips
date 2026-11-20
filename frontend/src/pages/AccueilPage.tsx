import { useVoyages } from "../api/requetes";
import CarteVoyage from "../composants/CarteVoyage";
import { EtatChargement, EtatErreur } from "../layout/Etats";
import styles from "./AccueilPage.module.css";

export default function AccueilPage() {
  const { data: voyages, error, refetch, isPending } = useVoyages();

  if (isPending) return <EtatChargement />;
  if (error) return <EtatErreur erreur={error} reessayer={refetch} />;

  return (
    <section className={styles.page}>
      <h1 className={styles.titre}>Voyages</h1>
      {voyages.length === 0 ? (
        <p className={styles.vide}>
          Aucun voyage pour l’instant. Importe un dossier avec <code>import_voyage</code>.
        </p>
      ) : (
        <ul className={styles.grille}>
          {voyages.map((v, i) => (
            <li key={v.slug}>
              <CarteVoyage voyage={v} priorite={i < 3} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
