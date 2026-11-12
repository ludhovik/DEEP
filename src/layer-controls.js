// GUI adapters keep the scientific parameters and existing rebuild callbacks
// authoritative. Presentation changes must not introduce a second view state.
export function matchingOptions(names, values, query = "") {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return names.map((label, i) => ({ label: String(label), value: values[i] }))
    .filter(item => terms.every(term => `${item.label} ${item.value}`.toLocaleLowerCase().includes(term)));
}

export function restoreLayerValues(params, initial, fallback, keys, validField = () => true) {
  for (const key of keys) {
    let value = Object.hasOwn(initial || {}, key) ? initial[key] : fallback[key];
    if (key.endsWith("Field") && !validField(key, value)) value = fallback[key];
    if (value === undefined || (key.endsWith("Field") && !validField(key, value))) continue;
    params[key] = value;
  }
}

export function moveControl(controller, folder) {
  const old = controller.parent;
  old.children.splice(old.children.indexOf(controller), 1);
  old.controllers.splice(old.controllers.indexOf(controller), 1);
  controller.parent = folder;
  folder.children.push(controller);
  folder.controllers.push(controller);
  folder.$children.append(controller.domElement);
}

// Reorder existing controllers instead of replacing them: cached references,
// listeners, disabled states and rebuild callbacks survive the new layout.
export function organiseLayer(folder, primary, positionFolders = [], trailingFolders = []) {
  const originalFolders = [...folder.folders];
  const advanced = folder.addFolder("Advanced").close();
  for (const controller of [...folder.controllers]) {
    if (!primary.includes(controller.property)) moveControl(controller, advanced);
  }
  for (const child of originalFolders) {
    if (positionFolders.includes(child) || trailingFolders.includes(child)) continue;
    folder.children.splice(folder.children.indexOf(child), 1);
    folder.folders.splice(folder.folders.indexOf(child), 1);
    child.parent = advanced;
    advanced.children.push(child);
    advanced.folders.push(child);
    advanced.$children.append(child.domElement);
    child.close();
  }
  const ordered = primary.map(key => folder.controllers.find(c => c.property === key)).filter(Boolean);
  const colourIndex = ordered.findIndex(c => /Scale$|Colormap$|ColourMode$/.test(c.property));
  ordered.splice(colourIndex < 0 ? ordered.length : colourIndex, 0, ...positionFolders);
  ordered.push(...trailingFolders, advanced);
  folder.children = ordered;
  for (const child of ordered) folder.$children.append(child.domElement);
  if (!advanced.children.length) advanced.hide();
  return advanced;
}

export function enhanceChoice(controller, gradient = null) {
  if (!controller.$select || controller.domElement.classList.contains("choice-enhanced")) return;
  const row = controller.domElement, document = row.ownerDocument;
  row.classList.add("choice-enhanced");
  controller.$select.hidden = true;
  controller.$display.hidden = true;
  const picker = document.createElement("details");
  picker.className = "layer-picker";
  const summary = document.createElement("summary");
  summary.setAttribute("aria-label", controller.$name.textContent);
  const selected = document.createElement("span");
  summary.append(selected);
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = gradient ? "Find a colour map…" : "Find a field…";
  search.setAttribute("aria-label", `Search ${controller.$name.textContent}`);
  search.autocomplete = "off";
  const list = document.createElement("div");
  list.className = "layer-picker-options";
  list.setAttribute("role", "group");
  list.setAttribute("aria-label", `${controller.$name.textContent} choices`);
  picker.append(summary, search, list);
  controller.$widget.append(picker);

  function swatch(parent, value) {
    if (!gradient) return;
    const preview = document.createElement("span");
    preview.className = "palette-swatch";
    preview.style.background = gradient(value);
    preview.setAttribute("aria-hidden", "true");
    parent.prepend(preview);
  }
  function select(value) {
    if (controller._disabled) return;
    controller.setValue(value);
    controller._callOnFinishChange();
    picker.open = false;
    summary.focus();
  }
  function render() {
    list.replaceChildren();
    const matches = matchingOptions(controller._names, controller._values, search.value);
    for (const item of matches) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.label;
      button.title = item.label;
      button.setAttribute("aria-pressed", String(item.value === controller.getValue()));
      swatch(button, item.value);
      button.addEventListener("click", () => select(item.value));
      button.addEventListener("keydown", event => {
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        const buttons = [...list.querySelectorAll("button")];
        const index = buttons.indexOf(button);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
          : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next]?.focus();
      });
      list.append(button);
    }
    if (!matches.length) {
      const empty = document.createElement("p");
      empty.textContent = "No matching fields or palettes.";
      empty.setAttribute("role", "status");
      list.append(empty);
    }
  }
  function sync() {
    const index = controller._values.indexOf(controller.getValue());
    selected.textContent = index < 0 ? String(controller.getValue()) : controller._names[index];
    summary.setAttribute("aria-label", `${controller.$name.textContent}: ${selected.textContent}`);
    summary.querySelector(".palette-swatch")?.remove();
    swatch(summary, controller.getValue());
    summary.title = selected.textContent;
    summary.setAttribute("aria-disabled", String(Boolean(controller._disabled)));
    summary.tabIndex = controller._disabled ? -1 : 0;
    if (controller._disabled) picker.open = false;
  }
  picker.addEventListener("toggle", () => {
    if (!picker.open) return;
    search.value = ""; render(); search.focus();
  });
  summary.addEventListener("click", event => { if (controller._disabled) event.preventDefault(); });
  search.addEventListener("input", render);
  search.addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const buttons = list.querySelectorAll("button");
      (event.key === "ArrowDown" ? buttons[0] : buttons[buttons.length - 1])?.focus();
    } else if (event.key === "Enter") {
      event.preventDefault(); list.querySelector("button")?.click();
    }
  });
  picker.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); picker.open = false; summary.focus(); }
  });
  picker.addEventListener("focusout", event => {
    if (!picker.contains(event.relatedTarget)) picker.open = false;
  });
  for (const method of ["updateDisplay", "disable", "options"]) {
    const original = controller[method];
    controller[method] = function (...args) {
      const result = original.apply(this, args);
      sync();
      if (method === "options" && picker.open) render();
      return result;
    };
  }
  sync();
}

export function addLayerOverview(gui, params, specs) {
  const overview = gui.addFolder("Visible layers");
  for (const spec of specs) {
    const original = spec.folder.controllersRecursive().find(c => c.property === spec.show);
    if (!original || spec.folder._hidden) continue;
    original.listen();
    const proxy = {};
    Object.defineProperty(proxy, "visible", {
      enumerable: true, get: () => params[spec.show], set: value => original.setValue(value),
    });
    const toggle = overview.add(proxy, "visible").name(spec.label).listen();
    const edit = gui.domElement.ownerDocument.createElement("button");
    edit.type = "button"; edit.textContent = "Edit"; edit.className = "layer-edit";
    edit.setAttribute("aria-label", `Edit ${spec.label}`);
    edit.addEventListener("click", () => {
      spec.folder.open();
      spec.folder.$title.focus();
      spec.folder.domElement.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    toggle.domElement.append(edit);
  }
  gui.children.splice(gui.children.indexOf(overview), 1);
  gui.children.unshift(overview);
  gui.$children.prepend(overview.domElement);
  overview.open();
  return overview;
}
