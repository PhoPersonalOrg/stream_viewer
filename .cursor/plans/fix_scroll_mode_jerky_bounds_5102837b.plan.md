# Fix Scroll Mode Jerky Bounds

## Problem Analysis

The jerky bounds issue occurs because of a timing mismatch in the update sequence:

1. **Current flow** (problematic):

- For each source in the loop:
    - `_prepare_display_heatmap()` reads the **current** (old) x-axis range from `pw.viewRange()`
    - Calculates what the **new** x-axis range should be
    - Updates x-axis to the new range
    - Sets image rect based on columns extracted from the **old** range
- This creates a feedback loop where the display is prepared for the old range, then the range changes, causing a mismatch

2. **Additional issues**:

- X-axis range calculation happens inside the loop for each source
- Each source might calculate slightly different ranges (different session times/buffer states)
- Only the bottom plot item actually applies the range update, but calculation happens for all sources
- The image rect is set based on columns extracted for the old range, but the x-axis shows the new range

## Solution

Restructure the update sequence to:

1. **Calculate x-axis range once** before the source loop (use the first source's state or a common calculation)
2. **Modify `_prepare_display_heatmap()`** to accept an optional `target_xrange` parameter
3. **Use the intended new range** when extracting display columns instead of reading the current range
4. **Update x-axis range once** after all sources are processed (or update it before preparing displays)

## Implementation Details

### Changes to `update_visualization()` method

1. **Pre-calculate x-axis range** (lines ~1158-1190):

- Move x-axis range calculation outside the source loop
- Calculate once using the first available source's state
- Store in a variable `target_xrange = (time_start, time_start + time_width)`

2. **Update x-axis range early** (before preparing displays):

- Update the x-axis range for the bottom plot item before the source loop (or at the start)
- This ensures `_prepare_display_heatmap()` reads the correct range

3. **Pass target range to `_prepare_display_heatmap()`**:

- Modify the call to pass `target_xrange` parameter
- This allows using the intended range instead of reading the current range

### Changes to `_prepare_display_heatmap()` method

1. **Add `target_xrange` parameter** (line ~826):

- Add optional parameter: `target_xrange: Optional[Tuple[float, float]] = None`
- If provided, use this instead of reading `pw.viewRange()`

2. **Use target range when available** (line ~856-880):

- When `target_xrange` is provided, use it to calculate column indices
- Fall back to `pw.viewRange()` only if `target_xrange` is None (for backward compatibility)

## Files to Modify

- [`stream_viewer/stream_viewer/renderers/heatmap_pg.py`](stream_viewer/stream_viewer/renderers/heatmap_pg.py)
- Modify `_prepare_display_heatmap()` method signature and logic (lines ~826-908)
- Restructure `update_visualization()` method to pre-calculate and use target x-axis range (lines ~1047-1233)

## Testing Considerations

- Verify smooth scrolling when new columns are added in Scroll mode