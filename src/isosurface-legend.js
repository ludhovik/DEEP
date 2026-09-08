// Use the committed mesh, so failed/pending requests never relabel the old figure.
export function isosurfaceLegendEntries(meshes) {
  return meshes.filter(mesh => mesh?.visible && mesh.material?.opacity > 0
      && mesh.geometry?.attributes?.position?.count > 0 && mesh.userData?.isoLegend)
    .map(mesh => ({ ...mesh.userData.isoLegend,
      color: `#${mesh.material.color.getHexString()}`,
      label: `${mesh.userData.isoLegend.field} = ${mesh.userData.isoLegend.value}` }));
}

export function updateIsosurfaceLegend(element, entries) {
  if (!element) return;
  element.style.display = entries.length ? "block" : "none";
  element.replaceChildren();
  if (!entries.length) return;
  const doc = element.ownerDocument;
  const heading = doc.createElement("div");
  heading.className = "legend-title";
  heading.textContent = "Isosurfaces";
  element.append(heading);
  for (const entry of entries) {
    const row = doc.createElement("div");
    row.className = "legend-row";
    const swatch = doc.createElement("span");
    swatch.className = "iso-legend-swatch";
    swatch.style.backgroundColor = entry.color;
    const label = doc.createElement("span");
    label.textContent = entry.label;
    row.append(swatch, label);
    element.append(row);
  }
}
