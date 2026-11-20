import { createBrowserRouter } from "react-router";
import Layout from "./layout/Layout";
import AccueilPage from "./pages/AccueilPage";
import IntrouvablePage from "./pages/IntrouvablePage";
import JourPage from "./pages/JourPage";
import VisionneusePage from "./pages/VisionneusePage";
import VoyagePage from "./pages/VoyagePage";

// L'URL reflète toujours l'écran : chaque état visible a son adresse, donc le
// bouton retour et les liens directs fonctionnent partout.
//
// La visionneuse est une route ENFANT de la page jour : la page jour reste
// montée dessous (scroll conservé), et c'est elle qui affiche la visionneuse
// via son <Outlet />.
export const router = createBrowserRouter([
  {
    element: <Layout />,
    // Une erreur de rendu inattendue reste dans le cadre du site.
    errorElement: <IntrouvablePage erreur />,
    children: [
      { index: true, element: <AccueilPage /> },
      { path: "voyages/:slug", element: <VoyagePage /> },
      {
        path: "voyages/:slug/jours/:date",
        element: <JourPage />,
        children: [{ path: "photos/:photoId", element: <VisionneusePage /> }],
      },
      { path: "*", element: <IntrouvablePage /> },
    ],
  },
]);
