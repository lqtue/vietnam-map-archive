import { coverageAreas } from './catalogAreas';

/** Six geographic browsing regions, mapped to the archive's pre-July-2025 provinces.
 * Source: https://en.baochinhphu.vn/six-socio-economic-development-zones-111221027163100671.htm
 * These are locators, not historical administrative units or post-merger provinces. */
export const CATALOG_REGIONS = [
  {
    key: 'northern-midlands-mountains',
    en: 'Northern Midlands & Mountains',
    vi: 'Trung du và miền núi Bắc Bộ',
    provinces: [
      'Hà Giang',
      'Cao Bằng',
      'Bắc Kạn',
      'Tuyên Quang',
      'Lào Cai',
      'Yên Bái',
      'Thái Nguyên',
      'Lạng Sơn',
      'Bắc Giang',
      'Phú Thọ',
      'Điện Biên',
      'Lai Châu',
      'Sơn La',
      'Hòa Bình',
    ],
  },
  {
    key: 'red-river-delta',
    en: 'Red River Delta',
    vi: 'Đồng bằng sông Hồng',
    provinces: [
      'Hà Nội',
      'Hải Phòng',
      'Hải Dương',
      'Hưng Yên',
      'Vĩnh Phúc',
      'Bắc Ninh',
      'Thái Bình',
      'Nam Định',
      'Hà Nam',
      'Ninh Bình',
      'Quảng Ninh',
    ],
  },
  {
    key: 'central-coast',
    en: 'North Central & Central Coast',
    vi: 'Bắc Trung Bộ và duyên hải miền Trung',
    provinces: [
      'Thanh Hóa',
      'Nghệ An',
      'Hà Tĩnh',
      'Quảng Bình',
      'Quảng Trị',
      'Thừa Thiên Huế',
      'Đà Nẵng',
      'Quảng Nam',
      'Quảng Ngãi',
      'Bình Định',
      'Phú Yên',
      'Khánh Hòa',
      'Ninh Thuận',
      'Bình Thuận',
    ],
  },
  {
    key: 'central-highlands',
    en: 'Central Highlands',
    vi: 'Tây Nguyên',
    provinces: ['Kon Tum', 'Gia Lai', 'Đắk Lắk', 'Đắk Nông', 'Lâm Đồng'],
  },
  {
    key: 'southeast',
    en: 'Southeast',
    vi: 'Đông Nam Bộ',
    provinces: [
      'Hồ Chí Minh',
      'Bình Dương',
      'Bình Phước',
      'Đồng Nai',
      'Tây Ninh',
      'Bà Rịa–Vũng Tàu',
    ],
  },
  {
    key: 'mekong-delta',
    en: 'Mekong Delta',
    vi: 'Đồng bằng sông Cửu Long',
    provinces: [
      'Cần Thơ',
      'Long An',
      'Tiền Giang',
      'Bến Tre',
      'Trà Vinh',
      'Vĩnh Long',
      'An Giang',
      'Đồng Tháp',
      'Kiên Giang',
      'Hậu Giang',
      'Sóc Trăng',
      'Bạc Liêu',
      'Cà Mau',
    ],
  },
] as const;

export function geographicRegions(row: { regions?: unknown; region?: unknown }): string[] {
  const areas = coverageAreas(row);
  return CATALOG_REGIONS.filter((region) =>
    areas.some((area) => (region.provinces as readonly string[]).includes(area))
  ).map((region) => region.key);
}

export function matchesGeographicRegion(
  row: { regions?: unknown; region?: unknown },
  selected: readonly string[]
): boolean {
  return !selected.length || geographicRegions(row).some((key) => selected.includes(key));
}
