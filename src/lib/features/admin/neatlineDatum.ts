/**
 * The datum presets an operator picks from when hand-entering GCP coordinates
 * off a sheet's printed graticule.
 *
 * The maths moved to `$lib/core/geo/datum.ts` in Sept 2026 so the location
 * search could use it too; what stays here is the labelled list, which is UI
 * copy and belongs with the editor that renders it.
 */
import { INDIAN_1960, type DatumParams } from '$lib/core/geo/datum';

export { shiftToWgs84, geographicToECEF, ecefToGeographic } from '$lib/core/geo/datum';

export interface DatumPreset extends DatumParams {
  label: string;
}

export const DATUM_PRESETS: DatumPreset[] = [
  {
    // EPSG:4131 — the datum explicitly printed on US Army / AMS maps
    // of Vietnam (including the Hà Tiên / Zone 48 series).
    // Everest 1830 Modified (EPSG:7018): a differs from the 1975/1954 variants.
    // towgs84 from EPSG transformation 1052 (mainland South Vietnam).
    label: 'Indian 1960 — EPSG:4131 · US Army AMS maps, southern Vietnam (Everest Mod.)',
    ...INDIAN_1960,
  },
  {
    // Con Son island variant — same datum, slightly different regional fit
    label: 'Indian 1960 — EPSG:4131 · Con Son Island variant (EPSG transform 1053)',
    a: 6377304.063,
    b: 6356103.038993155,
    dX: 182,
    dY: 915,
    dZ: 344,
  },
  {
    // Used on some Thai / northern-Vietnam sheets
    label: 'Indian 1975 — EPSG:4240 (Thailand / northern Indochina, Everest 1830 orig.)',
    a: 6377276.345,
    b: 6356075.41314024,
    dX: 210,
    dY: 814,
    dZ: 289,
  },
  {
    label: 'Indian 1954 — EPSG:4239 (alternative SE-Asia fit, Everest 1830 orig.)',
    a: 6377276.345,
    b: 6356075.41314024,
    dX: 217,
    dY: 823,
    dZ: 299,
  },
  {
    label: 'Pulkovo 1942 / Gauss-Krüger (Soviet-era Vietnamese maps, Krassowsky)',
    a: 6378245.0,
    b: 6356863.01877305,
    dX: 28,
    dY: -130,
    dZ: -95,
  },
];
