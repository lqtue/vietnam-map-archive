import { expect, test } from '@playwright/test';
import { observeImageInfoLoads } from '../src/lib/map/shell/warpedOverlay';

test('renderer-owned image requests handle lifecycle aborts without replacing promises', async () => {
  let reject!: (error: unknown) => void;
  const request = new Promise<void>((_resolve, fail) => {
    reject = fail;
  });
  const requests = [request];
  const errors: unknown[] = [];
  const renderer = { loadMissingImagesInViewport: () => requests };
  observeImageInfoLoads(renderer, (error) => errors.push(error));
  expect(renderer.loadMissingImagesInViewport()).toBe(requests);
  const aborted = new DOMException('Map destroyed', 'AbortError');
  reject(aborted);
  await Promise.resolve();
  expect(errors).toEqual([]);
  // The owner/awaiting consumers still receive the original cancellation.
  await expect(request).rejects.toBe(aborted);
});

test('renderer image request failures remain observable and reject awaiting consumers', async () => {
  const failure = new Error('Invalid IIIF image response');
  const request = Promise.reject<void>(failure);
  const errors: unknown[] = [];
  const renderer = { loadMissingImagesInViewport: () => [request] };
  observeImageInfoLoads(renderer, (error) => errors.push(error));
  expect(renderer.loadMissingImagesInViewport()[0]).toBe(request);
  await Promise.resolve();
  expect(errors).toEqual([failure]);
  await expect(request).rejects.toBe(failure);
});
