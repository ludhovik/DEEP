import test from 'node:test';
import assert from 'node:assert/strict';
import { useMobileLayout } from '../src/mobile-layout.js';

test('phone layout follows narrow screens and landscape touch phones, not desktop touch alone', () => {
  assert.equal(useMobileLayout('auto',390,844,true),true);
  assert.equal(useMobileLayout('auto',844,390,true),true);
  assert.equal(useMobileLayout('auto',1280,800,true),false);
  assert.equal(useMobileLayout('auto',1440,900,false),false);
  assert.equal(useMobileLayout('auto',600,900,false),true);
});
test('manual layout overrides automatic detection in either direction', () => {
  assert.equal(useMobileLayout('desktop',390,844,true),false);
  assert.equal(useMobileLayout('mobile',1440,900,false),true);
});
