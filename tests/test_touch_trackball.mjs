import test from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';
import { TouchTrackballControls } from '../src/touch-trackball-controls.js';

function setup() {
  const camera = new PerspectiveCamera(45,1,0.01,100);
  camera.position.set(0,0,5);
  const controls = new TouchTrackballControls(camera,null);
  Object.assign(controls.screen,{left:0,top:0,width:400,height:800});
  return {camera,controls};
}
function finger(id,x,y) {return {pointerId:id,pointerType:'touch',pageX:x,pageY:y};}
function down(c,p) {c._addPointer(p);c._onTouchStart(p);}
function up(c,p) {c._onTouchEnd(p);c._removePointer(p);}
function near(a,b) {assert.ok(a.distanceTo(b)<1e-12,`${a.toArray()} vs ${b.toArray()}`);}

test('off-centre pinch zooms without translating or rotating, including release',()=>{
  const {camera,controls:c}=setup();
  down(c,finger(1,150,300));
  c._lastAngle=.2;c._lastAxis.set(0,1,0); // preceding single-finger inertia
  down(c,finger(2,250,300));
  const target=c.target.clone(), direction=camera.position.clone().normalize(), upAxis=camera.up.clone();
  c._onTouchMove(finger(1,140,320));
  c._onTouchMove(finger(2,290,320));
  c.update();
  assert.ok(camera.position.length()<5);
  near(c.target,target);near(camera.position.clone().normalize(),direction);near(camera.up,upAxis);
  const position=camera.position.clone();
  up(c,finger(2,290,320));up(c,finger(1,140,320));
  for(let i=0;i<20;i++)c.update();
  near(c.target,target);near(camera.position,position);
});

test('a quick pinch released before the next animation frame leaves no delayed motion',()=>{
  const {camera,controls:c}=setup();
  down(c,finger(1,150,300));down(c,finger(2,250,300));
  c._onTouchMove(finger(1,180,330));c._onTouchMove(finger(2,300,330));
  up(c,finger(2,300,330));up(c,finger(1,180,330));c.update();
  near(c.target,new Vector3());near(camera.position,new Vector3(0,0,5));
});

test('explicit pan moves the target while finger separation cannot change zoom',()=>{
  const {camera,controls:c}=setup();c.touchGesture='pan';
  down(c,finger(1,150,300));down(c,finger(2,250,300));
  c._onTouchMove(finger(1,170,330));c._onTouchMove(finger(2,300,330));c.update();
  assert.ok(c.target.length()>0);
  assert.ok(Math.abs(camera.position.distanceTo(c.target)-5)<1e-12);
});

test('cancelling touch discards residual pan; mouse pan still works',()=>{
  const {controls:c}=setup();
  down(c,finger(1,150,300));down(c,finger(2,250,300));
  c._onTouchMove(finger(2,280,340));c._removePointer(finger(1));c._removePointer(finger(2));c.update();
  near(c.target,new Vector3());
  c._panEnd.set(.1,.1);c.update();assert.ok(c.target.length()>0);
});

test('one finger retains rotation',()=>{
  const {camera,controls:c}=setup();
  down(c,finger(1,150,300));c._onTouchMove(finger(1,190,320));c.update();
  assert.ok(camera.position.clone().normalize().distanceTo(new Vector3(0,0,1))>.01);
  near(c.target,new Vector3());
});

test('recentring preserves camera distance and angle and removes pending pan/rotation',()=>{
  const {camera,controls:c}=setup();
  c.target.set(1,2,3);camera.position.set(3,5,7);
  const offset=camera.position.clone().sub(c.target),up=camera.up.clone();
  c._zoomEnd.set(0,.2);c._panEnd.set(.2,.3);c._lastAngle=.5;c._lastAxis.set(1,0,0);
  c.recenter();c.update();
  near(c.target,new Vector3());near(camera.position,offset);near(camera.up,up);
});
