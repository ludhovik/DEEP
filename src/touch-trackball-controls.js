import { TrackballControls } from 'three/examples/jsm/controls/TrackballControls.js';

// Keep Trackball's desktop/one-finger controls, but separate pinch and pan.
export class TouchTrackballControls extends TrackballControls {
  constructor(camera, element) {
    super(camera, element);
    this.touchGesture = 'zoom';
    this.addEventListener('start', () => {
      if (this._pointers.filter(p => p.pointerType === 'touch').length >= 2) {
        this._hadTouchPair = true;
        this._settleTouchRotation();
      }
    });
  }

  recenter() {
    this.object.position.sub(this.target);
    this.target.set(0, 0, 0);
    this._panStart.copy(this._panEnd);
    this._zoomStart.copy(this._zoomEnd);
    this._touchZoomDistanceStart = this._touchZoomDistanceEnd = this._touchZoomDistanceEnd || 1;
    this._settleTouchRotation();
    this.update();
  }

  _settleTouchRotation() {
    this._movePrev.copy(this._moveCurr);
    this._lastAngle = 0;
  }

  update() {
    const paired = this._pointers.filter(p => p.pointerType === 'touch').length >= 2;
    if (paired) {
      this._hadTouchPair = true;
      this._settleTouchRotation();
      if (this.touchGesture === 'pan') {
        // Changing finger separation must not zoom while deliberately panning.
        this._touchZoomDistanceStart = this._touchZoomDistanceEnd;
      } else {
        // Discard midpoint motion rather than accumulating a deferred pan.
        this._panStart.copy(this._panEnd);
      }
    } else if (this._hadTouchPair) {
      // Release/cancellation must not apply a last pan or rotation impulse.
      this._panStart.copy(this._panEnd);
      this._touchZoomDistanceStart = this._touchZoomDistanceEnd;
      this._settleTouchRotation();
      this._hadTouchPair = false;
    }
    super.update();
  }
}
