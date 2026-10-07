// ---------------------------------------------------------------------------
//  SKYNODE SITE CONTENT
//
//  Every word on the page lives in this file. Edit the text between the
//  quotes, commit, and the site rebuilds itself.
//
//  Status labels: use exactly 'DONE', 'IN PROGRESS', or 'NEXT'.
//  The colour and icon of each row follow the label automatically.
//
//  Tip: if your text needs an apostrophe, keep the outer quotes as
//  backticks (`like this`) so you don't have to escape anything.
//
//  Every build checks this file first (scripts/check-content.mjs). If you
//  make a typo, the check names the line and what's wrong.
// ---------------------------------------------------------------------------

export const content = {
  meta: {
    title: 'Skynode | AI sky tracker',
    description:
      'A low-cost visual sensing platform, starting with one passive sky-tracking node. About $113 in new parts for the sensing hardware (camera, servos, mount, power), before the computer that runs the model.',
    // Public URL of the live site (used for social share previews).
    url: 'https://skynode-si.netlify.app/',
  },

  // VISIT COUNTER (GoatCounter: free, no cookies, nothing personal stored).
  // Off while empty. Sign up at goatcounter.com, pick a code (for example
  // 'skynode'), and put that code here. The privacy page updates itself.
  analytics: {
    goatcounter: 'bsalsa2',
  },

  nav: {
    brand: 'SKYNODE',
    links: [
      { label: 'How it works', href: '#how' },
      { label: 'Status', href: '#status' },
      { label: 'Roadmap', href: '#roadmap' },
    ],
  },

  hero: {
    eyebrow: 'PHASE 1 · AI SKY TRACKER',
    headline: 'A low-cost visual sensing platform, starting with one passive sky-tracking node.',
    sub: 'A camera, a model and a pan-tilt mount that watch the sky, follow what they see and log every sighting.',
    primary: { label: 'View the code', href: 'https://github.com/bsalsa2/skynode' },
    secondary: { label: 'See where it stands', href: '#status' },
    // Cost note, shown under the buttons. Keep the exclusions in the sentence.
    cost: 'About $113 in new parts for the sensing hardware (camera, servos, mount, power), before the computer that runs the model.',
    facts: ['Passive sensing only', 'Solar power planned', 'MIT licensed'],
    caption:
      'Concept visualization. Live footage replaces this once the hardware is built.',

    // The glass readout card in the hero. Its numbers move with the
    // simulated aircraft crossing the sky behind it.
    card: {
      label: 'NODE-01 · CONCEPT',
      state: 'TRACKING',
      target: 'AIRCRAFT',
    },

    // REAL FOOTAGE: leave video empty until real footage exists.
    // When it does: put a short video file in web/public/media/ and set
    // video to its path, for example 'media/first-track.mp4'. It replaces the
    // concept visualization at the top of the page (muted, looping; paused
    // for visitors who turn off motion).
    // Before publishing a clip, check it doesn't show your house, street, or
    // anything that reveals where you live.
    footage: {
      video: '',
      poster: '', // optional still image, for example 'media/first-track.jpg'
      caption: '', // required once video is set: say what the clip shows
    },
  },

  math: {
    heading: 'The math is backwards',
    // Words inside [square brackets] light up white; the rest stay grey.
    statement: 'A small drone costs [a few hundred dollars.] Systems built to detect one cost [tens of thousands.]',
    stats: [
      { label: 'A small drone', value: '$100s' },
      { label: 'Typical detection system', value: '$10,000s' },
      { label: 'Skynode sensing parts, before the computer', value: '~$113', highlight: true },
    ],
    // Printed under the numbers so they can't be read as a capability claim.
    statsNote: 'Price comparison only, not a capability comparison. Skynode is one passive camera node and has not run on real hardware yet.',
    body: 'Skynode is a first step toward making that sensing layer cheap enough to put anywhere.',
    useCases: {
      tag: 'USE CASES',
      text: `Early use cases I'm exploring: farms, small airports, stadiums, and power substations. First hypothesis to test: small general-aviation airfields.`,
    },
  },

  how: {
    kicker: 'System',
    heading: 'How it works',
    steps: [
      {
        number: '01',
        title: 'SENSE',
        metric: '28,526 IMAGES',
        body: 'A YOLO object-detection model looks at the camera feed and picks out aircraft and drones. It is training now on a dataset of 28,526 labeled images.',
      },
      {
        number: '02',
        title: 'TRACK',
        metric: 'P92.5 T47.0',
        body: 'A Raspberry Pi Pico drives two small servos on a pan-tilt mount, turning the camera to keep the target centered.',
      },
      {
        number: '03',
        title: 'LOG',
        metric: 'TIME · CLASS · CONF',
        body: 'Every sighting will be saved with the time, what it was, how confident the model was, and which way the camera was pointing.',
      },
    ],
    // 3D viewer of the pan-tilt mount, built from the STL files in /hardware.
    mount: {
      label: 'PAN-TILT MOUNT',
      caption:
        'Rendered live from the CAD files in this repo, with the two servos drawn as outlines, and moved through its pan and tilt axes. The physical build is next.',
      parts: [
        { name: 'BASE', text: 'Holds the pan servo, shaft up, and screws down with four M3 screws.' },
        { name: 'YOKE', text: 'Sits on the pan horn, holds the tilt servo, and carries the M3 pivot.' },
        { name: 'CAMERA ARM', text: 'Webcam cradle on the tilt horn and pivot.' },
      ],
    },
    // Simulated sensor view: what the node's on-screen overlay will look like.
    sensor: {
      label: 'SENSOR VIEW · SIMULATED',
      caption:
        'A simulation of the overlay the node draws on its camera feed (brain/overlay.py). The locked target gets the bold box and a solid label; anything else gets a thin box. The camera turns to keep the lock in the centre ring.',
    },
    note: 'The test range is free: real air traffic passes overhead all day. Planes publicly broadcast their positions (ADS-B), so I can compare what the camera saw with what actually flew over and report real accuracy numbers.',
  },

  status: {
    kicker: 'Where it stands',
    heading: 'Status',
    items: [
      { label: 'DONE', text: 'Pico servo firmware: smooth motion, calibration, command protocol' },
      { label: 'DONE', text: 'Detection + tracking loop, working in simulation, 200 automated tests' },
      { label: 'DONE', text: 'Pan-tilt mount designed in CAD, with STEP and STL files' },
      { label: 'DONE', text: 'Wiring diagram and bill of materials' },
      { label: 'IN PROGRESS', text: 'Detection model training: v3 with drone and aircraft classes' },
      { label: 'NEXT', text: 'Build the physical hardware. Nothing has run on real hardware yet.' },
      { label: 'NEXT', text: 'Sighting logger' },
      { label: 'NEXT', text: 'Live dashboard' },
      { label: 'NEXT', text: 'Test against real flight data (ADS-B) and publish accuracy results' },
      { label: 'NEXT', text: 'Pi 4 + solar deployment' },
    ],
  },

  // ACCURACY RESULTS: this section stays hidden until items has entries.
  // Only add numbers you have actually measured, and fill in source with how
  // and when they were measured. The build refuses numbers without a source.
  results: {
    heading: 'Results so far',
    intro: 'The v2 model, run on 43 real-world videos of planes, military jets and drones. This tests the model on recorded video. It is not a hardware test.',
    items: [
      { value: '7.5%', label: 'False-drone rate on real aircraft', note: '798 of 10,657 frames were called a drone' },
      { value: '0.8%', label: 'Civilian planes called drones' },
      { value: '10.8%', label: 'Military jets called drones', note: 'Mostly distant F-35s' },
    ],
    source: 'Model v2, 43 real-world videos. v3 (drone and aircraft classes, 960 px input) is in training. There are no v3 results yet.',
  },

  // KNOWN LIMITS: what Skynode can't do, stated plainly.
  limits: {
    kicker: 'Honest limits',
    heading: 'Known limits',
    items: [
      {
        tag: 'RANGE · ESTIMATE',
        text: 'A wide-lens webcam detects small drones only at short range, likely tens of meters (an estimate, still to be measured). Aircraft are detectable much farther.',
      },
      {
        tag: 'CONDITIONS',
        text: 'Visual sensing is weaker in darkness, fog and rain.',
      },
      {
        tag: 'NOT REMOTE ID',
        text: 'It can see drones that broadcast nothing, unlike Remote ID, but it does not replace Remote ID or RF sensors.',
      },
      {
        tag: 'NOT BUILT YET',
        text: 'Nothing has run on real hardware yet.',
      },
    ],
  },

  build: {
    heading: 'About me',
    body: `I'm Braden, I'm 14, and I like building things that work in the real world. I started with Sunnode, a small server that runs entirely on solar power from a panel on my fence. Then I got curious about drones, trained my first detection model, and Skynode was the next step. I've run a backyard gardening business, and I shelved a software startup after learning how hard it is to sell to companies when you're 13. I'm fascinated by geopolitics and technology, and I want to build an aerospace and defense company someday. Skynode is where I'm starting.`,
    // Personal quote, shown under the text and signed with your first name.
    quote: 'You only live once so go out there and make the most of every moment by chasing your dreams and living without regret',
    signature: 'Braden',
  },

  roadmap: {
    kicker: 'Roadmap',
    heading: 'From one node to a company',
    // The long-term vision lives here, not in the hero.
    intro: 'This is Phase 1. The long-term goal is autonomy for missile and drone detection and defense systems.',
    phases: [
      {
        phase: 'PHASE 1 · NOW',
        title: 'One working node',
        body: 'A camera that detects, tracks, and logs aircraft and drones, with real accuracy numbers.',
      },
      {
        phase: 'PHASE 2',
        title: 'A network of nodes',
        body: 'Several nodes working together can work out where a drone is and where it is heading.',
      },
      {
        phase: 'PHASE 3',
        title: 'Autonomous drones',
        body: 'For inspection, search and rescue, and drone detection and defense systems, built on the same sensing and tracking brain.',
      },
      {
        phase: 'PHASE 4',
        title: 'A company',
        body: `An aerospace and defense company building autonomy for missile and drone detection and defense systems, once I'm old enough to start one.`,
      },
    ],
    closing:
      'Phase 1 is passive by design. It carries no payloads, never jams, and never transmits on aircraft or drone frequencies. It only watches.',
  },

  // Card linking to the sister project, shown above the footer.
  sister: {
    label: 'Sister project',
    name: 'Sunnode',
    description: '', // optional: one sentence about what Sunnode is
    href: 'https://github.com/bsalsa2/sunnode',
    linkLabel: 'View on GitHub',
  },

  footer: {
    brand: 'SKYNODE',
    links: [
      { label: 'Skynode on GitHub', href: 'https://github.com/bsalsa2/skynode' },
      { label: 'Sister project: Sunnode', href: 'https://github.com/bsalsa2/sunnode' },
      { label: 'Privacy', href: './privacy.html' },
    ],
    contactLabel: 'Contact',
    email: 'bradensalcetti@icloud.com',
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
        text: 'Everything on this site, including the fonts, scripts, and 3D models, is served from the site itself. Your browser makes no requests to other companies while you read it.',
        textWithAnalytics: 'Everything on this site, including the fonts, scripts, and 3D models, is served from the site itself. The one exception is the visit counter described below.',
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
