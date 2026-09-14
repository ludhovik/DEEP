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
    label: "Early Earth — lava-world analogue (NASA artwork)",
    file: "assets/surfaces/early-earth-nasa.png",
    credit: "Early Earth visual analogue using NASA/VTAD's 55 Cancri e lava-world artwork; reprojection by DEEPscope. Not an Earth reconstruction.",
    sourceUrl: "https://science.nasa.gov/resource/55-cancri-e-3d-model/",
  },
  super_earth: {
    label: "Super-Earth — Proxima b (NASA artwork)",
    file: "assets/surfaces/super-earth-proxima-b.jpg",
    credit: "Proxima b: NASA Visualization Technology Applications and Development (VTAD). Artist's concept; surface and clouds are speculative.",
    sourceUrl: "https://science.nasa.gov/resource/proxima-b-3d-model/",
  },
  planetesimal: {
    label: "Asteroid — Bennu (NASA/OSIRIS-REx)",
    file: "assets/surfaces/asteroid-bennu.jpg",
    credit: "Bennu: NASA/Goddard/University of Arizona, OSIRIS-REx/PolyCam global mosaic. Displayed on a sphere; Bennu's irregular shape is not modelled.",
    sourceUrl: "https://osiris-rex.lpl.arizona.edu/bennu_global_mosaic/",
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
