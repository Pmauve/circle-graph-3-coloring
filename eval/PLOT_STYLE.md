# Plot Style Conventions

These conventions are for paper-facing figures. Exploratory notebooks or
debug plots may be looser, but final figures should use `eval.plot_style`.

- Output paper figures as vector `pdf`. Use `png` only for previews.
- Use the shared one-column and two-column figure-size presets.
- Use serif/math-compatible matplotlib fonts so plots match LaTeX reasonably well.
- Do not put titles inside plots; explain the figure in the LaTeX caption.
- Keep axis labels short and include units, for example `Generation time (ms)`.
- Use stable colors for each generator/solver family across all plots.
- Also vary marker shapes and line styles so plots remain readable in grayscale.
- Use legends consistently and avoid covering data; move the legend outside when needed.
- Use log scales only when the data span multiple orders of magnitude, and make this clear in filenames/captions.
- For generator-family plots with enough seeds, prefer median curves with shaded 25--75% empirical quantile bands.
- For very small exploratory runs, prefer means with min/max error bars over over-interpreting quantiles.
- Captions should state what points and error bars represent.
- Plot filenames should describe paper concepts rather than temporary script names.
- When useful, generate both combined multi-panel PDFs and individual component PDFs.
