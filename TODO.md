# TODO

This file stores a list of tasks that are not yet implemented in this project. 
It is meant to be a living document that is updated as new tasks are identified and completed.
Tasks are categorized into three types: cosmetic, documentational, and feature.
A task is an idea in the [IDEAS.md](IDEAS.md) file that has been deemed worth implementing.

---

**2026-09-14 Batch**

- [x] cosmetic: in side bar in instance plot window,
    - [x] stack buttons "Clear" and "All recorded" vertically to save horizontal space;
    - [x] rename "Signature of {fault class}" to "Signature" to save horizontal space.
- [x] cosmetic: add texture to "Unknown" status colorbox in Help -> Well status for consistency with instance plots.
- [x] documentational: in Help -> Variables, say what position number the sensor occupies relative to the illustration (use the 3W 2.0.0 paper).
- [x] documentational: comment on and illustrate fault signatures (use the 3W 2.0.0 paper).
- [x] feature: a checkbox in the main window that joins instances with overlapping time ranges.
    > [!CAUTION]
    > Join is only valid if there is no labeling disagreement within the overlapping time range,
    > i.e., if the earlier instance has label "X" or "Unknown" (NaN), then the latter instance must have label "X" or "Unknown" as well. 
    > Otherwise, the instances cannot be joined.
    
    > [!TIP]
    > If instances come from different fault folders, but have valid join, 
    > the resulting instance box should present the colors of all its parents. 

---