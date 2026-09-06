// Local reference imagery, loaded only when selected. Full provenance and
// redistribution terms are shipped in public/assets/surfaces/CREDITS.txt.
export const SURFACE_TEXTURES = Object.freeze({
  earth: {
    label: "Earth",
    file: "assets/earth_blue_marble.png",
    credit: "Earth: NASA/Goddard Scientific Visualization Studio.",
    sourceUrl: "https://svs.gsfc.nasa.gov/2915/",
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
