# Cartes de Mayotte

Cartes vectorielles libres de Mayotte, prêtes à l'emploi : silhouettes, découpages administratifs, relief, lagon, routes et sentiers, cartes de situation. En SVG pour l'affichage, en GeoJSON et TopoJSON pour les applications cartographiques.

**Cartes dans le domaine public (CC0 1.0)** : utilisables partout, y compris dans un projet commercial, sans demander l'autorisation. Les silhouettes, le lagon et les cartes de situation sont libres sans aucune condition. Les autres cartes reprennent des données de l'IGN : en les réutilisant, citez « Source : IGN » (voir [Quelle mention pour quelle carte](#quelle-mention-pour-quelle-carte)).

*English summary below.*

## Les cartes

| Famille | Fichier | Contenu |
|---|---|---|
| Silhouettes | `dist/svg/silhouette/mayotte.svg` | Grande-Terre, Petite-Terre et les îlots, détail standard (35 Ko) |
| | `mayotte-detailed.svg` | Tracé à 5 m près, pour l'impression (140 Ko) |
| | `mayotte-simple.svg` | Pour une icône ou un logo, petits îlots retirés (5 Ko) |
| | `mayotte-outline.svg` | Trait de côte seul |
| | `mayotte-lagoon.svg` | L'île, le lagon et les récifs |
| Administratif | `dist/svg/administrative/communes.svg` | Les 17 communes |
| | `cantons.svg` | Les 13 cantons |
| | `epci.svg` | Les 5 intercommunalités |
| | `villages.svg` | 105 villages et lieux-dits habités, sur le fond des communes |
| | `places.svg` | Tous les lieux nommés (684) : villages, quartiers, lieux-dits, plages, sommets, îlots… |
| Physique | `dist/svg/physical/relief.svg` | Relief en aplats de 100 m |
| | `hydrography.svg` | Cours d'eau permanents et mangroves |
| | `lagoon.svg` | Lagon, récifs et hauts-fonds, version détaillée |
| | `vegetation.svg` | Couvert végétal en 6 classes : forêt, bosquets, landes, bananeraies, vergers, mangroves (370 Ko) |
| | `protected-areas.svg` | 41 espaces protégés nommés (réserves naturelles, Conservatoire du littoral, forêts publiques…), estran et plans d'eau |
| Réseaux | `dist/svg/network/roads-main.svg` | Routes nationales et départementales, une forme par numéro, et liaisons maritimes (99 Ko) |
| | `roads-full.svg` | Réseau routier complet : près de 1 300 km de routes, rues, chemins et pistes, avec le nom des rues (798 Ko) |
| | `trails.svg` | Sentiers et escaliers, routes principales en blanc pour se repérer (705 Ko) |
| Bâti et équipements | `dist/svg/built/services.svg` | 935 équipements nommés (écoles, santé, services publics, lieux de culte, sport, ports, aéroport…), sur le fond des communes |
| Situation | `dist/svg/situation/mozambique-channel.svg` | Mayotte entre l'Afrique et Madagascar |
| | `comoros-archipelago.svg` | Mayotte dans l'archipel des Comores |

La galerie `index.html` présente toutes les cartes, avec téléchargement et copie du code.

Les mêmes couches existent en données géographiques, en WGS84 (longitude, latitude) :

- `dist/geojson/mayotte-<couche>.geojson`, une couche par fichier : `land`, `lagoon`, `reef`, `communes`, `cantons`, `epci`, `villages`, `places`, `rivers`, `mangroves`, `relief`, `vegetation`, `protected_areas`, `intertidal`, `lakes`, `roads` (routes et liaisons maritimes), `trails` (sentiers et escaliers), `services` ;
- `dist/topojson/mayotte.json`, toutes les couches dans un seul fichier léger. Pour rester léger, il garde les routes numérotées et les liaisons maritimes, mais regroupe le reste du réseau et les sentiers par classe, sans le nom des rues : ces noms sont dans les GeoJSON `roads` et `trails`.

## Utiliser les SVG

### Les identifiants

Chaque forme porte un `id` stable et des attributs `data-*` :

| Carte | `id` | Attributs |
|---|---|---|
| Communes | `commune-97611` (code INSEE) | `data-code`, `data-name` |
| Cantons | `canton-97606` (code INSEE du canton) | `data-code`, `data-name` |
| Intercommunalités | `epci-200060457` (SIREN) | `data-code`, `data-name` |
| Villages | `village-97611-kaweni` (commune + nom) | `data-name`, `data-commune` |
| Lieux nommés | `place-97611-kaweni`, `place-97611-hamaha-summit` pour un homonyme | `data-name`, `data-kind`, `data-commune` |
| Relief | `relief-300` (altitude du niveau) | `data-above_m` |
| Routes numérotées | `route-n1`, `route-d4a` (numéro) | `data-ref` (`N1`, `D4A`…), `data-kind` (`national`, `departmental`), `data-name` quand la route porte un nom |
| Liaisons maritimes | `ferry-mamoudzou-dzaoudzi-barge` (nom) | `data-kind` (`ferry`), `data-name` |
| Rues, chemins, sentiers | — (pas d'`id`) | `data-kind`, et `data-name`, `data-commune` (code INSEE) quand la voie a un nom |
| Équipements | `facility-97611-college-de-kwale`, `facility-97604-mosquee-du-vendredi-worship-2` pour un homonyme | `data-name`, `data-kind`, `data-commune` |
| Végétation | `vegetation-mangrove` (classe) | `data-kind`, `data-area_ha` |
| Espaces protégés | `protected-reserve-naturelle-nationale-de-l-ilot-mbouzi` (nom), `protected-n-gouja-biotope-protection` pour un homonyme | `data-name`, `data-kind`, `data-area_ha` |
| Estran, plans d'eau | `intertidal`, `lake-dziana-dzaha` (nom) | `data-name` (sauf l'estran et une lagune sans nom), `data-kind`, `data-area_ha` |
| Situation | `mayotte`, `mayotte-locator`, `country-mdg`… | — |

Les noms sont les noms officiels du Code officiel géographique (par exemple « Bandrele », sans accent).

### Changer les couleurs

Les couleurs livrées sont des attributs de présentation : n'importe quelle règle CSS les remplace.

```html
<style>
  #communes path { fill: #f2efe8; stroke: #999; }
  #commune-97611 { fill: #d1495b; }          /* Mamoudzou */
  path[data-code^="9760"]:hover { fill: #edae49; }
</style>
```

Pour que le CSS de la page s'applique, le SVG doit être **intégré dans le HTML** (copié dans la page ou injecté en JavaScript). Une balise `<img>` affiche la carte, mais ne laisse pas le CSS y entrer.

### Superposer les cartes

Toutes les cartes de l'île partagent l'un de deux cadres, et se superposent au pixel près :

- **cadre île** : silhouettes (sauf `mayotte-lagoon`), administratif, `relief`, `hydrography`, `vegetation`, `protected-areas`, réseaux, `services` ;
- **cadre lagon** : `mayotte-lagoon`, `lagoon`.

Exemple : le relief sous les limites de communes, en empilant `relief.svg` puis `communes.svg` avec un remplissage transparent.

### Les lieux nommés

`places.svg` réunit tous les lieux nommés de la BD TOPO, y compris ceux qui ne sont pas des villages. L'attribut `data-kind` donne le type de lieu :

| `data-kind` | Lieux | Nombre |
|---|---|---|
| `village` | villages (lieux-dits habités) | 105 |
| `neighbourhood` | quartiers | 190 |
| `locality` | lieux-dits non habités | 46 |
| `wood`, `tree` | bois et arbres remarquables | 11 |
| `beach` | plages | 187 |
| `summit`, `pass`, `rocks`, `escarpment`, `isthmus` | sommets, cols, rochers… | 66 |
| `islet`, `cape`, `reef` | îlots, caps et pointes, récifs | 80 |

Pour n'afficher qu'un type de lieu :

```css
#places circle { display: none; }
#places circle[data-kind="beach"] { display: inline; }
```

Les noms suivent l'orthographe de l'IGN. Un lieu absent de la BD TOPO n'apparaît pas : la carte reflète ce que l'IGN a recensé, pas tous les noms en usage.

### Végétation et espaces protégés

`vegetation.svg` regroupe les zones de végétation de la BD TOPO en une forme par classe (`data-kind`) :

| `data-kind` | Classe BD TOPO | Surface |
|---|---|---|
| `broadleaf-forest` | Forêt fermée de feuillus | 22 283 ha |
| `shrubland` | Lande ligneuse | 1 729 ha |
| `banana-plantation` | Bananeraie | 1 305 ha |
| `orchard` | Verger | 766 ha |
| `mangrove` | Mangrove (même vert que `hydrography.svg`) | 685 ha |
| `woodlot` | Bois (bosquets de moins de 5 ha) | 150 ha |

Pour garder un fichier léger, les taches de moins d'un hectare sont retirées du SVG, sauf les bosquets, tous petits. Le GeoJSON garde tout.

`protected-areas.svg` montre les espaces protégés nommés, l'estran (sable et galets découverts à marée basse) et les plans d'eau. Les formes se chevauchent : la réserve des forêts recouvre en partie les forêts publiques, le site Ramsar et l'arrêté de biotope de N'Gouja recouvrent des terrains du Conservatoire.

| `data-kind` | Espaces | Nombre |
|---|---|---|
| `departmental-forest`, `state-forest` | forêts départementales et domaniales | 9 + 3 |
| `nature-reserve` | réserves naturelles nationales (forêts de Mayotte, îlot Mbouzi) | 2 |
| `coastal-conservancy` | terrains du Conservatoire du littoral | 24 |
| `ramsar-site` | site Ramsar de la vasière des Badamiers | 1 |
| `biotope-protection` | arrêtés de protection de biotope | 2 |
| `intertidal` | estran | 1 |
| `lake`, `reservoir`, `coastal-lagoon` | lac Dziani Dzaha, retenues collinaires, lagune | 5 |

Le Parc naturel marin de Mayotte n'y figure pas : il couvre toute la zone économique exclusive (63 700 km²), bien au-delà du cadre de l'île. Les noms suivent l'orthographe de l'IGN (« Dziana Dzaha » pour le lac Dziani Dzaha).

### Les routes et sentiers

Les trois cartes de réseaux sont dessinées sur la silhouette de l'île. L'attribut `data-kind` donne la classe de chaque voie :

| `data-kind` | Voies | Longueur |
|---|---|---|
| `national` | routes nationales N1 à N4, une forme par numéro | 89 km |
| `departmental` | routes départementales (26 numéros, de D1 à D19 et DX) | 147 km |
| `ferry` | liaisons maritimes : barge et amphidrome Mamoudzou – Dzaoudzi, départs vers Moroni et Mutsamudu | 17 km |
| `secondary` | autres routes principales, non numérotées | 77 km |
| `local` | routes et rues de desserte | 371 km |
| `track` | chemins et routes empierrées | 593 km |
| `trail` | sentiers (`trails.svg`) | 882 km |
| `steps` | escaliers (`trails.svg`) | 30 km |

`roads-main.svg` contient les classes `national`, `departmental` et `ferry` ; `roads-full.svg`, toutes les classes de routes. Les rues, chemins et sentiers sont regroupés par nom de voie et par commune (adresses BAN) : une voie nommée est une seule forme, les tronçons sans nom d'une classe en forment une autre. Seules les voies en service sont retenues. La seule route numérotée qui porte un nom sur toute sa longueur est la D9, « Route de Moya ».

Pour n'afficher que les routes nationales :

```css
#roads path { display: none; }
#roads path[data-kind="national"] { display: inline; }
```

### Les équipements

`services.svg` place un point sur chaque équipement nommé de la BD TOPO (zones d'activité ou d'intérêt, ports, gares maritimes et routières, aéroport). L'emprise de l'aéroport, sa piste et le port de Longoni sont dessinés en aplat sous les points (`service-area-airport`, `service-area-runway`, `service-area-port`). L'attribut `data-kind` donne la catégorie :

| `data-kind` | Équipements | Nombre |
|---|---|---|
| `education` | écoles, collèges, lycées, université, centres de formation | 361 |
| `health` | hôpitaux, centres de consultation, PMI, accueil des personnes handicapées | 28 |
| `administration` | mairies, préfecture, services de l'État et du Département, poste, France services… | 128 |
| `security` | gendarmerie, police, pompiers, casernes, prison | 25 |
| `worship` | mosquées, églises, tombeaux | 97 |
| `public-space` | places, parcs et jardins | 74 |
| `culture` | bibliothèques, musées, salles de spectacle, vestiges | 38 |
| `sport` | stades, terrains, gymnases, piscines, sports nautiques | 101 |
| `tourism` | offices de tourisme, farés et aires de repos, hébergements de loisirs | 19 |
| `transport` | aéroport, ports, gares maritimes et routière, parking relais | 18 |
| `economy` | marchés, zones industrielles, centrales, déchèteries, eau potable, épuration | 46 |

Les équipements « en projet » sont écartés, ceux « en construction » sont gardés. Comme pour les lieux nommés, la carte reflète ce que l'IGN a recensé et nommé.

### Aucun texte dans les cartes

Les SVG ne contiennent aucune étiquette : chacun ajoute les siennes, dans sa langue et sa police. Les noms sont dans les attributs `data-name`, et les centres des villages sont donnés par les cercles de `villages.svg`.

### Avec D3

```js
const topo = await fetch("dist/topojson/mayotte.json").then((r) => r.json());
const communes = topojson.feature(topo, topo.objects.communes);
const projection = d3.geoMercator().fitSize([600, 800], communes);
d3.select("svg").selectAll("path")
  .data(communes.features)
  .join("path")
  .attr("d", d3.geoPath(projection))
  .attr("fill", (d) => color(myData[d.properties.code]));
```

## Comment les cartes sont faites

- **Projection des SVG** : RGM04 / UTM zone 38 Sud (EPSG:4471), la projection officielle de Mayotte. Elle est conforme (formes et angles exacts), nord en haut. Les cartes de situation sont en projection azimutale équivalente de Lambert, centrée sur la région.
- **Côte, îlots, récifs et lagon** : tracés à partir d'images satellite Sentinel-2 du 2 septembre 2025 (quatre tuiles, moins de 0,6 % de nuages), à 10 m de résolution :
  - terre : indice d'eau NDWI négatif, hors nuages ; 373,5 km² mesurés pour 374 km² officiels ;
  - récifs et hauts-fonds : eau à forte réflectance verte ;
  - lagon : enveloppe convexe du système récifal, ramenée à 2,5 km au plus de tout récif ou de toute terre, puis lissée.
- **Communes, cantons, intercommunalités, villages, cours d'eau, mangroves** : données IGN, simplifiées sans trou ni chevauchement entre voisins.
- **Relief** : modèle numérique BD ALTI de l'IGN, au pas de 25 m.
- **Végétation, espaces protégés, estran, plans d'eau** : BD TOPO de l'IGN ; la végétation est fusionnée par classe.
- **Routes et sentiers** : tronçons de route de la BD TOPO, classés par numéro, nature et importance, assemblés bout à bout et simplifiés à 10 m.

### Limites connues

- **Le contour du lagon est une interprétation.** Sur la côte ouest, la barrière récifale est trop profonde pour se voir sur l'image ; le contour la relie en ligne presque droite. À l'est, il déborde par endroits d'environ 1 km au-delà du récif.
- Les zones de récif mêlent récif barrière, récif frangeant, herbiers et hauts-fonds : ce sont les zones peu profondes visibles depuis l'espace, pas une cartographie des habitats.
- La côte des cartes administratives (IGN) et celle des silhouettes (Sentinel-2) diffèrent légèrement. Chaque famille reste cohérente avec elle-même.
- Pas de courbes de profondeur du lagon dans cette version.
- Les routes viennent de l'IGN et la côte de Sentinel-2 : en bord de mer, une route peut déborder de quelques mètres sur l'eau ou s'arrêter avant le rivage.
- Les liaisons vers Moroni et Mutsamudu s'arrêtent à quelques kilomètres au nord de Dzaoudzi : la BD TOPO ne les trace que dans les eaux de Mayotte.

## Reconstruire les cartes

Il faut Python 3 et Node.js. Environ 190 Mo de données sont téléchargés, sans compte.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
npm install
```

```bash
npm run all
```

Les étapes peuvent se lancer séparément : `npm run fetch` (téléchargements), `npm run prepare-data` (tracés et extraction), `npm run build` (SVG, GeoJSON, TopoJSON, catalogue de la galerie).

## Sources

- IGN – Admin Express COG, édition 2026 ; BD TOPO, édition du 15 septembre 2026 ; BD ALTI 25 m. Licence Ouverte Etalab 2.0. **Toute réutilisation de ces données doit mentionner l'IGN**, quelle que soit la licence de nos cartes.
- Contient des données Copernicus Sentinel-2 modifiées (2025), via AWS Open Data.
- Natural Earth (domaine public), pour les pays voisins des cartes de situation.

## Licences

- Cartes et données (`dist/`) : [CC0 1.0](LICENSE), domaine public, sous réserve de la mention IGN ci-dessous.
- Code (`scripts/`, `index.html`) : [MIT-0](LICENSE-CODE).

### Quelle mention pour quelle carte

La Licence Ouverte de l'IGN suit ses données partout : nous ne pouvons pas lever l'obligation de le citer.

| Cartes | Données | Origine | Mention à faire |
|---|---|---|---|
| Silhouettes (`mayotte*.svg`), `lagoon.svg` | `land`, `lagoon`, `reef` | Sentinel-2, tracé par nous | Aucune |
| Cartes de situation | — | Natural Earth et notre silhouette | Aucune |
| `communes.svg`, `cantons.svg`, `epci.svg` | `communes`, `cantons`, `epci` | IGN – Admin Express | « Source : IGN – Admin Express » |
| `villages.svg`, `places.svg` | `villages`, `places` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `hydrography.svg` | `rivers`, `mangroves` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `relief.svg` | `relief` | IGN – BD ALTI | « Source : IGN – BD ALTI » |
| `vegetation.svg` | `vegetation` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `protected-areas.svg` | `protected_areas`, `intertidal`, `lakes` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `roads-main.svg`, `roads-full.svg` | `roads` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `trails.svg` | `trails`, `roads` | IGN – BD TOPO | « Source : IGN – BD TOPO » |
| `services.svg` | `services` | IGN – BD TOPO | « Source : IGN – BD TOPO » |

`villages.svg`, `places.svg` et `services.svg` reprennent aussi le fond des communes : leur mention couvre donc Admin Express et BD TOPO (« Source : IGN – Admin Express, BD TOPO »). Le TopoJSON regroupe toutes les couches et demande la mention de l'IGN.

Pour les cartes libres de toute mention, une ligne « Contient des données Copernicus Sentinel-2 modifiées » reste bienvenue, sans être imposée à ceux qui reprennent nos cartes.

Auteur : Jean-Luc Petit.

---

## English summary

Free vector maps of Mayotte: outlines, administrative divisions (communes, cantons, EPCI, villages), relief, rivers and mangroves, vegetation cover, protected natural areas, lagoon and reefs, road network and footpaths, facilities and services, and locator maps. SVG files carry stable ids and `data-*` attributes and no text labels; GeoJSON and TopoJSON are in WGS84. Island maps share common frames and overlay exactly. Coastline, reefs and lagoon were traced from Sentinel-2 imagery and carry no conditions, like the locator maps. Administrative divisions, villages, named places, facilities, rivers, mangroves, vegetation, protected areas, roads, footpaths and relief come from IGN data under the Licence Ouverte: reusing them requires the credit “Source: IGN”. Maps are released under CC0 1.0, subject to that credit; code under MIT-0.
