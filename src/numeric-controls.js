// Keep lil-gui-specific behaviour here: number edits must finish without blur,
// and scrolling the panel must not accidentally change an unfocused control.
export function steppedValue(value, direction, { step = 1, min = -Infinity, max = Infinity, fast = false } = {}) {
  if (!Number.isFinite(value) || !Number.isFinite(step) || step <= 0) return value;
  const next = Math.round((value + direction * step * (fast ? 10 : 1)) / step) * step;
  return Math.min(max, Math.max(min, Number(next.toPrecision(14))));
}

const INSTRUCTIONS = "Drag or type a value. Select a control to use arrow keys or the mouse wheel. Shift: 10 steps. Slider Home / End: minimum / maximum.";

export function enhanceNumericControls(gui) {
  const document = gui.domElement.ownerDocument;
  for (const controller of gui.controllersRecursive()) {
    const row = controller.domElement;
    if (!row.classList.contains("lil-number") || row.classList.contains("numeric-enhanced")) continue;
    row.classList.add("numeric-enhanced");
    const input = controller.$input, slider = controller.$slider;
    const buttons = [];
    let timer = null, destroyed = false;
    const clearTimer = () => { clearTimeout(timer); timer = null; };
    const finish = () => {
      clearTimer();
      if (!destroyed && row.isConnected && !controller._disabled) controller._callOnFinishChange();
    };
    const scheduleFinish = () => { clearTimer(); timer = setTimeout(finish, 180); };
    const label = () => controller.$name.textContent;
    input.title = INSTRUCTIONS;
    input.setAttribute("role", "spinbutton");
    if (slider) {
      slider.title = INSTRUCTIONS;
      slider.setAttribute("role", "slider");
      slider.setAttribute("aria-labelledby", controller.$name.id);
      slider.setAttribute("aria-orientation", "horizontal");
      for (const [direction, symbol, action] of [[-1, "−", "Decrease"], [1, "+", "Increase"]]) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `numeric-step numeric-${action.toLowerCase()}`;
        button.textContent = symbol;
        button.addEventListener("click", event => {
          change(direction, event.shiftKey);
          finish();
        });
        controller.$widget.appendChild(button);
        buttons.push({ button, action });
      }
      // Moving from the value box to the track must release input focus, so
      // lil-gui updates the number throughout a mouse drag.
      slider.addEventListener("mousedown", () => {
        if (!controller._disabled) slider.focus({ preventScroll: true });
      }, true);
    }

    function sync() {
      const value = controller.getValue(), disabled = Boolean(controller._disabled);
      for (const element of [input, slider].filter(Boolean)) {
        element.setAttribute("aria-valuenow", String(value));
        element.setAttribute("aria-disabled", String(disabled));
        for (const [attribute, bound] of [["aria-valuemin", controller._min], ["aria-valuemax", controller._max]]) {
          if (Number.isFinite(bound)) element.setAttribute(attribute, String(bound));
          else element.removeAttribute(attribute);
        }
      }
      if (slider) slider.tabIndex = disabled ? -1 : 0;
      for (const { button, action } of buttons) {
        button.disabled = disabled;
        button.setAttribute("aria-label", `${action} ${label()}`);
        button.title = `${action} ${label()} by ${controller._step} (Shift: 10 steps)`;
      }
    }

    function change(direction, fast = false, bound = null) {
      if (destroyed || controller._disabled) return;
      const value = document.activeElement === input ? Number.parseFloat(input.value) : Number(controller.getValue());
      if (!Number.isFinite(value)) return;
      const next = bound ?? steppedValue(value, direction, {
        step: controller._step, min: controller._min, max: controller._max, fast,
      });
      controller.setValue(next);
      // lil-gui intentionally leaves a focused text input alone; arrow/wheel
      // changes are complete numbers and need their display updated now.
      input.value = String(controller.getValue());
      sync();
    }

    row.addEventListener("keydown", event => {
      if (event.altKey || event.ctrlKey || event.metaKey || controller._disabled) return;
      // Keep left/right caret movement and Home/End text selection in inputs.
      const isTrack = event.target === slider;
      let direction = 0, bound = null;
      if (event.key === "ArrowUp" || (isTrack && event.key === "ArrowRight")) direction = 1;
      if (event.key === "ArrowDown" || (isTrack && event.key === "ArrowLeft")) direction = -1;
      if (isTrack && event.key === "Home") bound = controller._min;
      if (isTrack && event.key === "End") bound = controller._max;
      if (!direction && bound === null) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      change(direction, event.shiftKey, bound);
      scheduleFinish();
    }, true);
    row.addEventListener("keyup", event => {
      if (timer && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) finish();
    }, true);
    row.addEventListener("wheel", event => {
      // Suppress lil-gui's hover-to-edit handler, but allow normal page scroll
      // and browser Ctrl-wheel zoom when this control isn't being adjusted.
      event.stopImmediatePropagation();
      if (!row.contains(document.activeElement) || controller._disabled || event.ctrlKey || event.metaKey) return;
      const delta = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? -event.deltaY : event.deltaX;
      if (!delta) return;
      event.preventDefault();
      change(Math.sign(delta), event.shiftKey);
      scheduleFinish();
    }, { capture: true, passive: false });
    row.addEventListener("focusout", event => {
      if (!row.contains(event.relatedTarget)) finish();
    });

    // Preserve existing callbacks/listeners, including updates from loaded view
    // codes and disabled-state changes. Cancel delayed edits on dataset reload.
    for (const method of ["updateDisplay", "disable"]) {
      const original = controller[method];
      controller[method] = function (...args) {
        const result = original.apply(this, args);
        if (this._disabled) clearTimer();
        sync();
        return result;
      };
    }
    const destroy = controller.destroy;
    controller.destroy = function (...args) {
      destroyed = true;
      clearTimer();
      return destroy.apply(this, args);
    };
    sync();
  }
}
