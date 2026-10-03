import { expect, test } from '@playwright/test';
import { groupSheetScans } from '../src/lib/data/maps/service';
import { isPrintingHeld } from '../src/lib/data/maps/sheetSources';
import { matchesSeriesFacet } from '../src/lib/data/maps/seriesFacet';

test('series facets use stable keys after a display label changes and omit unresolved maps', () => {
  const facet = ['l7014-test'];
  expect(matchesSeriesFacet({ series_key: 'l7014-test', collection: 'Renamed label' }, facet)).toBe(
    true
  );
  expect(matchesSeriesFacet({ series_key: null, collection: 'L7014 Test' }, facet)).toBe(false);
  expect(matchesSeriesFacet({ series_key: 'other-series', collection: 'L7014 Test' }, facet)).toBe(
    false
  );
});

test('separate scans group only when a reviewed printing identity is shared', () => {
  const grouped = groupSheetScans([
    { id: 'scan-a', printing_id: 'printing-a' },
    { id: 'scan-b', printing_id: 'printing-a' },
    { id: 'scan-c', printing_id: null },
    { id: 'scan-d', printing_id: null },
  ]);

  expect(grouped).toHaveLength(3);
  expect(grouped[0]).toMatchObject({ printingId: 'printing-a', unresolved: false });
  expect(grouped[0].scans.map((scan) => scan.id)).toEqual(['scan-a', 'scan-b']);
  expect(grouped.slice(1).map((group) => group.scans[0].id)).toEqual(['scan-c', 'scan-d']);
  expect(grouped.slice(1).every((group) => group.unresolved && group.printingId === null)).toBe(
    true
  );
});

test('institution holdings require an explicit printing or source-item link', () => {
  const row = { id: 'item-a', printing_id: null };
  expect(isPrintingHeld(row, [{ printing_id: null, source_item_id: null }])).toBe(false);
  expect(isPrintingHeld(row, [{ printing_id: 'other-printing', source_item_id: null }])).toBe(
    false
  );
  expect(isPrintingHeld(row, [{ printing_id: null, source_item_id: 'item-a' }])).toBe(true);
  expect(
    isPrintingHeld({ id: 'item-b', printing_id: 'printing-a' }, [
      { printing_id: 'printing-a', source_item_id: null },
    ])
  ).toBe(true);
});
