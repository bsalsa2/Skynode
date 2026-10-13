import { CONTACT_EMAIL } from './config.js';

// ---------------------------------------------------------------------------
//  VARN SITE CONTENT
//
//  Every word on the page lives in this file. Edit the text between the
//  quotes, commit, and the site rebuilds itself.
//
//  The layout follows the approved design in docs/design/home-mockup.webp:
//  hero, how it works, test results, the road ahead, footer.
//
//  Tip: if your text needs an apostrophe, keep the outer quotes as
//  backticks (`like this`) so you don't have to escape anything.
//
//  Every build checks this file first (scripts/check-content.mjs). If you
//  make a typo, the check names the line and what's wrong.
// ---------------------------------------------------------------------------

export const content = {
  meta: {
    title: 'Varn | Watch the sky',
    description:
      'Passive airspace awareness, built one research prototype at a time. Software tested on recorded video and in simulation; physical hardware validation pending.',
    // Public URL of the live site (used for social share previews). The
    // GitHub Pages workflow sets SITE_URL so its build points at the Pages
    // address; every other build (Netlify) uses the address below.
    url: process.env.SITE_URL || 'https://skynode-si.netlify.app/',
  },

  // VISIT COUNTER (GoatCounter: free, no cookies, nothing personal stored).
  // Off while empty. Sign up at goatcounter.com, pick a code (for example
  // 'varn'), and put that code here. The privacy page updates itself.
  analytics: {
    goatcounter: 'bsalsa2',
  },

  nav: {
    brand: 'VARN',
    // href: '#section' for this page, or a full https:// address.
    links: [
      { label: 'Home', href: '#top' },
      { label: 'Project', href: '#project' },
      { label: 'Results', href: '#results' },
      { label: 'Docs', href: 'https://github.com/bsalsa2/varn/tree/main/docs' },
      { label: 'About', href: 'https://github.com/bsalsa2/varn#readme' },
    ],
    github: { label: 'GitHub', href: 'https://github.com/bsalsa2/varn' },
  },

  hero: {
    eyebrow: 'VARN',
    // The last word is set in steel blue.
    headline: 'Watch the sky.',
    sub: 'Passive airspace awareness, built one research prototype at a time.',
    primary: { label: 'Explore the project', href: '#project' },
    secondary: { label: 'View results', href: '#results' },
    // The row along the bottom: what exists today. Keep it accurate.
    stage: 'Research prototype',
    facts: ['Software tested', 'Simulation results', 'Hardware build pending'],
    tagline: ['Safer skies.', 'More awareness.'],
    // Shown beside the tracking frame: the drone photo is an illustration.
    trackLabel: 'SAMPLE',
  },

  project: {
    kicker: 'How it works',
    heading: ['AI-powered', 'airspace detection.'],
    body: 'VARN uses computer vision and AI to detect, classify, and track airborne objects — from drones to aircraft — in real time. Our goal is simple: cleaner skies and safer airspace.',
    steps: [
      { icon: 'eye', title: 'Detect', text: 'Finds objects in the sky.' },
      { icon: 'brain', title: 'Classify', text: 'Uses AI to identify what it is.' },
      { icon: 'shield', title: 'Inform', text: 'Provides clear, actionable data.' },
    ],
    // The dashboard panel is a simulation: every value in it is made up.
    // feedLabel must contain the word SAMPLE.
    feedLabel: 'SAMPLE FEED',
    objectsLabel: 'Detected objects',
    objects: [
      { name: 'UAV', value: '0.87', kind: 'uav' },
      { name: 'Plane', value: '0.96', kind: 'plane' },
      { name: 'Bird', value: '0.12', kind: 'bird' },
      { name: 'Helicopter', value: '0.05', kind: 'heli' },
    ],
    readouts: ['ALT: 312 m', 'RANGE: 2.4 km', 'MODE: AI DETECTION'],
  },

  // TEST RESULTS: only numbers you have actually measured, with source saying
  // how and when. The build refuses a result without a source.
  results: {
    kicker: 'Test results',
    heading: 'Real data. Real limits.',
    body: `We've tested our AI model on recorded video and simulation data. The results show promise, but also highlight the challenges — especially with false classifications and limited accuracy in early models.`,
    button: { label: 'View detailed results', href: 'https://github.com/bsalsa2/varn#results-so-far' },
    cards: [
      { icon: 'crosshair', title: 'Drone detection', value: '14.9%', caption: ['accuracy in first model', '(drone clips only)'] },
      { icon: 'plane', title: 'False classifications', value: '7.5%', caption: ['of aircraft frames misidentified', 'as drones'] },
    ],
    conditions: {
      icon: 'database',
      title: 'Test conditions',
      items: ['Recorded video (43 clips)', 'Simulation environment', 'Limited dataset (early stage)'],
      link: { label: 'See full methodology', href: 'https://github.com/bsalsa2/varn/blob/main/training/README.md' },
    },
    source: 'Model v2 on 43 real-world videos of planes, military jets and drones (recorded video, not a hardware test). 14.9% = drone clips labeled correctly. 7.5% = 798 of 10,657 aircraft frames called a drone.',
  },

  roadmap: {
    kicker: 'The road ahead',
    heading: 'From prototype to platform.',
    // One line per entry, as broken in the design (joined into a paragraph on phones).
    body: [
      `Next, we'll build and test the physical hardware,`,
      'grow the training data, and improve detection accuracy.',
      `Long term, we're aiming to create a scalable system`,
      'for broader airspace awareness and real-world use cases.',
    ],
    button: { label: 'View the project roadmap', href: 'https://github.com/bsalsa2/varn#roadmap' },
    // when: put real dates here once you have them (for example 'Q1 2027').
    steps: [
      { when: 'Next', text: 'Build hardware prototype' },
      { when: 'Then', text: 'Field testing & validation' },
      { when: 'After that', text: 'Improve AI model & accuracy' },
      { when: 'Long term', text: 'Scale and expand capabilities' },
    ],
  },

  footer: {
    brand: 'VARN',
    tagline: 'Safer skies. More awareness.',
    links: [
      { label: 'GitHub', href: 'https://github.com/bsalsa2/varn' },
      { label: 'Docs', href: 'https://github.com/bsalsa2/varn/tree/main/docs' },
      { label: 'Contact', href: `mailto:${CONTACT_EMAIL}` },
    ],
    // Varn Labs is an organization label, not a company. The code is MIT licensed.
    copyright: '© 2026 Varn Labs. MIT licensed.',
    privacy: { label: 'Privacy', href: './privacy.html' },
    contactLabel: 'Contact',
    email: CONTACT_EMAIL,
  },

  // ---- Privacy policy page (privacy.html) ---------------------------------
  // Update the date whenever you change this page.
  privacy: {
    title: 'Privacy policy',
    updated: 'October 4, 2026',
    intro: `This site doesn't collect personal information. There are no accounts, forms, cookies, analytics, ads, or trackers.`,
    // Used instead of intro when the visit counter is on.
    introWithAnalytics: `This site doesn't collect personal information. There are no accounts, forms, cookies, ads, or trackers. It counts visits anonymously, as explained below.`,
    sections: [
      {
        heading: 'What the site loads',
        text: 'Everything on this site, including the fonts, scripts, and images, is served from the site itself. Your browser makes no requests to other companies while you read it.',
        textWithAnalytics: 'Everything on this site, including the fonts, scripts, and images, is served from the site itself. The one exception is the visit counter described below.',
      },
      {
        // Only shown when the visit counter is on.
        onlyWithAnalytics: true,
        heading: 'Visit counts',
        text: `To see how many people visit, this site uses GoatCounter, a privacy-friendly counter. It records which page was viewed, the site you came from, your browser, screen size, and country. It uses no cookies and doesn't store your IP address or anything that identifies you.`,
        link: { label: `GoatCounter's privacy policy`, href: 'https://www.goatcounter.com/help/privacy' },
      },
      {
        heading: 'Hosting',
        text: `The site is hosted by Netlify. Like any web host, Netlify's servers handle each visit and may keep standard technical logs, such as IP addresses and browser type, to run and protect the service. This site adds no tracking on top of that.`,
        link: { label: `Netlify's privacy policy`, href: 'https://www.netlify.com/privacy/' },
      },
      {
        heading: 'Links to other sites',
        text: 'Links to GitHub take you to GitHub, which has its own privacy policy.',
      },
      {
        heading: 'How this site is made',
        text: 'I design the system, train the model, and am building the hardware. Most of the code, including this website, is written with Claude Code, an AI coding tool, working from my designs. I say so everywhere I share this project.',
      },
      {
        heading: 'Changes',
        text: 'If anything here changes, this page will be updated, along with the date at the top.',
      },
    ],
    contactText: 'Questions about this page? Email',
  },
};
