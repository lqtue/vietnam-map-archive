import { expect, test } from '@playwright/test';
import { createStudioMeasurementController } from '../src/lib/features/annotate/studioMeasurement';
import type { FeatureCollection } from 'geojson';

const empty: FeatureCollection = { type: 'FeatureCollection', features: [] };
const drawn: FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [106.7, 10.8] },
      properties: { label: 'Test annotation' },
    },
  ],
};

function harness() {
  const events: string[] = [];
  const controller = createStudioMeasurementController((event) => events.push(event));
  return { controller, events };
}

test('project entry and unchanged features do not start a draft or report a save', () => {
  const { controller, events } = harness();
  controller.beginProject(empty);
  controller.open();

  expect(controller.observeDraft(empty)).toBe(false);
  expect(controller.saved(empty, true)).toBe(false);
  expect(events).toEqual(['contribution_open']);
});

test('first feature change starts one draft; only confirmed nonempty save succeeds', () => {
  const { controller, events } = harness();
  controller.beginProject(empty);

  expect(controller.observeDraft(drawn)).toBe(true);
  expect(controller.observeDraft(drawn)).toBe(false);
  expect(controller.saved(drawn, false)).toBe(false);
  expect(controller.saved(drawn, true)).toBe(true);
  expect(controller.observeDraft(drawn)).toBe(false);
  expect(events).toEqual(['draft_started', 'save_success']);
});

test('deleting saved features is a draft, but an empty save has no success event', () => {
  const { controller, events } = harness();
  controller.beginProject(drawn);

  expect(controller.observeDraft(empty)).toBe(true);
  expect(controller.saved(empty, true)).toBe(false);
  expect(controller.observeDraft(drawn)).toBe(true);
  expect(events).toEqual(['draft_started', 'draft_started']);
});

test('beginning another project resets its feature baseline and draft attempt', () => {
  const { controller, events } = harness();
  controller.beginProject(drawn);
  controller.observeDraft(empty);
  controller.beginProject(empty);

  expect(controller.observeDraft(drawn)).toBe(true);
  expect(events).toEqual(['draft_started', 'draft_started']);
});
