import { createContext, useContext, useEffect, useState } from "react";
import { ChefDeLecture } from "../lib/lecture";

/** Chef de lecture des photos animées de la galerie (null hors galerie : visionneuse…). */
export const ContexteLecture = createContext<ChefDeLecture | null>(null);

export const useChefDeLecture = () => useContext(ContexteLecture);

/** Crée le chef de lecture d'une galerie ; `suspendu` : visionneuse ouverte. */
export function useNouveauChefDeLecture(suspendu: boolean): ChefDeLecture | null {
  const [chef, setChef] = useState<ChefDeLecture | null>(null);
  useEffect(() => {
    const c = new ChefDeLecture();
    setChef(c);
    return () => c.detruire();
  }, []);
  useEffect(() => {
    chef?.suspendre(suspendu);
  }, [chef, suspendu]);
  return chef;
}
