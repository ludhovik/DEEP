// Local reference imagery, loaded only when selected. Full provenance and
// redistribution terms are shipped in public/assets/surfaces/CREDITS.txt.
export const SURFACE_TEXTURES = Object.freeze({
  sun: {
    label: "Sun",
    file: "assets/surfaces/sun.jpg",
    credit: "Sun: Solar System Scope / INOVE, CC BY 4.0 (illustrative solar imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  earth: {
    label: "Earth",
    file: "assets/earth_blue_marble.png",
    credit: "Earth: NASA/Goddard Scientific Visualization Studio.",
    sourceUrl: "https://svs.gsfc.nasa.gov/2915/",
  },
  rodinia: {
    label: "Earth — Rodinia (1 billion years ago)",
    file: "assets/surfaces/rodinia-1000ma.png",
    credit: "Rodinia, 1000 Ma: DEEPscope rendering of Li et al. (2008) / EarthByte, CC BY 4.0. Tectonic blocks, not ancient coastlines.",
    sourceUrl: "https://doi.org/10.1016/j.precamres.2007.04.021",
  },
  early_earth: {
    label: "Early Earth (lava artwork)",
    file: "assets/surfaces/early-earth.png",
    credit: "Early Earth illustration: Lava004 by ambientCG / Lennart Demes, CC0 1.0; spherical adaptation by DEEPscope. Artistic lava surface.",
    sourceUrl: "https://ambientcg.com/view?id=Lava004",
  },
  super_earth: {
    label: "Super-Earth exoplanet (artwork)",
    file: "assets/surfaces/super-earth.jpg",
    credit: "Hypothetical rocky super-Earth: cubicApocalypse (2025), via Celestia, CC BY 4.0. Generic exoplanet artwork, not an observed surface.",
    sourceUrl: "https://github.com/CelestiaProject/CelestiaContent/blob/62de0d22bae6428d06a900fd3e045fa8d2b969ad/textures/hires/rocky.jpg.license",
  },
  planetesimal: {
    label: "Asteroid / planetesimal (artwork)",
    file: "assets/surfaces/asteroid.jpg",
    credit: "Generic asteroid / planetesimal: cubicApocalypse (2023), via Celestia, CC BY 4.0. Illustrative texture on a sphere.",
    sourceUrl: "https://github.com/CelestiaProject/CelestiaContent/blob/62de0d22bae6428d06a900fd3e045fa8d2b969ad/textures/hires/asteroid.jpg.license",
  },
  mars: {
    label: "Mars",
    file: "assets/surfaces/mars.jpg",
    credit: "Mars: Solar System Scope / INOVE, CC BY 4.0 (NASA-derived imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  ganymede: {
    label: "Ganymede",
    file: "assets/surfaces/ganymede.jpg",
    credit: "Ganymede: Askaniy Anpilogov and NASA image contributors, CC BY 3.0. Full credits below.",
    sourceUrl: "https://github.com/CelestiaProject/CelestiaContent/blob/1993a082ee6307c0df7fdc0828eb117a0e8e9958/textures/hires/ganymede.jpg.license",
  },
  jupiter: {
    label: "Jupiter",
    file: "assets/surfaces/jupiter.jpg",
    credit: "Jupiter: Solar System Scope / INOVE, CC BY 4.0 (NASA-derived imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  saturn: {
    label: "Saturn",
    file: "assets/surfaces/saturn.jpg",
    credit: "Saturn: Solar System Scope / INOVE, CC BY 4.0 (NASA-derived imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  mercury: {
    label: "Mercury",
    file: "assets/surfaces/mercury.jpg",
    credit: "Mercury: Solar System Scope / INOVE, CC BY 4.0 (NASA-derived imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  venus: {
    label: "Venus (radar surface)",
    file: "assets/surfaces/venus.jpg",
    credit: "Venus radar surface: Solar System Scope / INOVE, CC BY 4.0 (NASA-derived imagery).",
    sourceUrl: "https://www.solarsystemscope.com/textures/",
  },
  enceladus: {
    label: "Enceladus",
    file: "assets/surfaces/enceladus.jpg",
    credit: "Enceladus: NASA/JPL/Space Science Institute; map border removed by Ysogo.",
    sourceUrl: "https://www.jpl.nasa.gov/images/pia08417-map-of-enceladus/",
  },
  moon: {
    label: "Moon",
    file: "assets/surfaces/moon.jpg",
    credit: "Moon: NASA’s Scientific Visualization Studio, LRO / LROC / LOLA.",
    sourceUrl: "https://svs.gsfc.nasa.gov/4720/",
  },
});

export const SURFACE_TEXTURE_OPTIONS = Object.freeze(Object.fromEntries(
  Object.entries(SURFACE_TEXTURES).map(([id, surface]) => [surface.label, id])
));
