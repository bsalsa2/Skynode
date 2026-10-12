// Section slots. render.js renders these at build time, in page order:
//
//   hero, [afterHero], ticker, math, [afterMath], story, [afterStory],
//   labels, [afterLabels], how, [afterHow], status, [afterStatus], results,
//   limits, [afterLimits], about, roadmap + outro, [beforeFooter], footer
//
// Each slot is a list of functions (content, next) => html. Call next() once
// for the section's number in its "01-00 [ LABEL ] +" marker. A new section
// lives in its own file here (sections/<name>.js), with its static CSS in
// sections/<name>.css (main.js includes every sections/*.css in the build).
// Copy belongs in content.js so it can be edited in one place.

export const SLOTS = {
  afterHero: [],
  afterMath: [],
  afterStory: [],
  afterLabels: [],
  afterHow: [],
  afterStatus: [],
  afterLimits: [],
  beforeFooter: [],
};
