/**
 * Pure checks for the province locator behind `maps.region` / `region_2025` (mig 109). No browser,
 * no network — the boundary file is replaced by two squares.
 *
 * They exist because the 63 → 34 table is typed by hand and a slip in it would file a sheet under
 * the wrong province on a public page with no error anywhere, and because the rule that keeps a
 * Cambodian sheet off a Vietnamese province lives in one function that is easy to loosen.
 */
import { test, expect } from '@playwright/test';
import { makeLocator, regionOf, provinceNow } from '../scripts/lib/regionOf.mjs';

const OLD_63 = [
  'An Giang',
  'Bà Rịa–Vũng Tàu',
  'Bình Dương',
  'Bình Phước',
  'Bình Thuận',
  'Bình Định',
  'Bạc Liêu',
  'Bắc Giang',
  'Bắc Kạn',
  'Bắc Ninh',
  'Bến Tre',
  'Cao Bằng',
  'Cà Mau',
  'Cần Thơ',
  'Gia Lai',
  'Hồ Chí Minh',
  'Hà Giang',
  'Hà Nam',
  'Hà Nội',
  'Hà Tĩnh',
  'Hòa Bình',
  'Hưng Yên',
  'Hải Dương',
  'Hải Phòng',
  'Hậu Giang',
  'Khánh Hòa',
  'Kiên Giang',
  'Kon Tum',
  'Lai Châu',
  'Long An',
  'Lào Cai',
  'Lâm Đồng',
  'Lạng Sơn',
  'Nam Định',
  'Nghệ An',
  'Ninh Bình',
  'Ninh Thuận',
  'Phú Thọ',
  'Phú Yên',
  'Quảng Bình',
  'Quảng Nam',
  'Quảng Ngãi',
  'Quảng Ninh',
  'Quảng Trị',
  'Sóc Trăng',
  'Sơn La',
  'Thanh Hóa',
  'Thái Bình',
  'Thái Nguyên',
  'Thừa Thiên Huế',
  'Tiền Giang',
  'Trà Vinh',
  'Tuyên Quang',
  'Tây Ninh',
  'Vĩnh Long',
  'Vĩnh Phúc',
  'Yên Bái',
  'Điện Biên',
  'Đà Nẵng',
  'Đắk Lắk',
  'Đắk Nông',
  'Đồng Nai',
  'Đồng Tháp',
];

test('the 63 provinces fold into exactly 34', () => {
  expect(OLD_63).toHaveLength(63);
  const now = new Set(OLD_63.map(provinceNow));
  expect(now.size).toBe(34);
  expect(provinceNow('Bình Dương')).toBe('Hồ Chí Minh');
  expect(provinceNow('Thừa Thiên Huế')).toBe('Huế');
  expect(provinceNow('Hà Nội')).toBe('Hà Nội');
});

const square = (name: string, x0: number, y0: number, x1: number, y1: number) => ({
  properties: { shapeName: name },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [x0, y0],
        [x1, y0],
        [x1, y1],
        [x0, y1],
        [x0, y0],
      ],
    ],
  },
});
const vn = makeLocator({
  features: [square('Long An', 0, 0, 1, 1), square('Hồ Chí Minh', 1, 0, 2, 1)],
});
const kh = makeLocator({ features: [square('Cambodia', -1, 0, 0, 1)] });

test('a sheet takes the province under most of it, not the one under its centre', () => {
  // Centre (0.95) is in Long An; two thirds of the sheet is in Hồ Chí Minh.
  expect(regionOf([0.5, 0.1, 1.4, 0.2], vn, kh)).toMatchObject({ region: 'Long An' });
  expect(regionOf([0.9, 0.1, 1.8, 0.2], vn, kh)).toMatchObject({
    region: 'Hồ Chí Minh',
    region_2025: 'Hồ Chí Minh',
  });
});

test("open water keeps its province; a neighbour's land does not", () => {
  // Mostly sea to the north of Long An: still Long An.
  expect(regionOf([0.1, 0.8, 0.9, 1.4], vn, kh)?.region).toBe('Long An');
  // Mostly Cambodia, a sliver of Vietnam: null.
  expect(regionOf([-0.6, 0.1, 0.05, 0.4], vn, kh)).toBeNull();
  // All sea: null.
  expect(regionOf([3, 3, 3.1, 3.1], vn, kh)).toBeNull();
});

test('country-scale and missing bboxes get no region', () => {
  expect(regionOf([0, 0, 1.9, 1], vn, kh)).not.toBeNull();
  expect(regionOf([-5, 0, 3, 1], vn, kh)).toBeNull(); // 8° wide
  expect(regionOf(null, vn, kh)).toBeNull();
  expect(regionOf([1, 2, 3], vn, kh)).toBeNull();
});
