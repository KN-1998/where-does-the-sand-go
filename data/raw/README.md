# Historical shoreline input

`Hatteras_Transects.dbf` and `hatteras_transects_metadata.txt` were copied
unchanged from the local handoff's USGS Hatteras GIS bundle. The batch history
diagnostic records the DBF SHA-256. The source metadata identifies NAD83 UTM
zone 18N, historical shoreline periods, and processing details.

Selection is fixed before examining rates: `3937500 <= StartY <= 3942500`
metres. Missing/nonfinite values and numeric missing sentinels below -999 are
excluded per field. No rate-based outlier selection is performed. This window
is a historical geographic diagnostic, not a verified mapping of the synthetic
5 km future corridor. Overlapping periods cannot supply independent train and
validation sets. Do not claim posterior calibration or independent validation
from these aggregate rates alone.


Source metadata caveats verified in the supplied text:

- Lines 195–199 say the DSAS *default accuracy* was 4.4 m. Repository notes
  also mention 4.5–4.8 m positional uncertainty. These are not established as
  the same statistic; neither is a rate confidence interval. Do not turn either
  number into an observed per-transect slope standard error.
- The DAS_km definition at line 423 refers to Fire Island/Moriches Inlet,
  inconsistent with a Hatteras dataset. This appears to be a metadata template
  carryover. The diagnostic deliberately selects StartY instead; lines 351–375
  explicitly define StartX/StartY as UTM18N NAD83 metres, retained attribute
  coordinates even after geographic reprojection.
- Lines 399 and 407 explicitly define the LRR fields in m/yr with positive
  accretion and negative erosion, based on 14 and 9 shorelines respectively.
