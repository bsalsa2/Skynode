import { CONTACT_EMAIL } from './config.js';

// ---------------------------------------------------------------------------
//  VARN SITE CONTENT
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
    title: 'Varn | Watch the sky',
    description:
      'A low-cost visual sensing platform, starting with one passive sky-tracking node. About $113 in new parts for the sensing hardware (camera, servos, mount, power), before the computer that runs the model.',
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
    links: [
      { label: 'Overview', href: '#top' },
      { label: 'How it works', href: '#story' },
      { label: 'Results', href: '#results' },
      { label: 'Status', href: '#status' },
    ],
  },

  hero: {
    // Shown in [ square brackets ] above the headline.
    eyebrow: 'A watcher, not a weapon',
    headline: 'Watch the sky.',
    // What exists today, shown right under the headline. Keep it accurate.
    stage: {
      label: 'Research prototype',
      text: 'Software tested on recorded video and in simulation. Physical hardware validation pending.',
    },
    sub: 'Passive visual sensing that tells drones from aircraft and logs every sighting.',
    primary: { label: 'View the code', href: 'https://github.com/bsalsa2/varn' },
    secondary: { label: 'See where it stands', href: '#status' },
    // Cost note, shown under the buttons. Keep the exclusions in the sentence.
    cost: 'Estimated sensing-hardware parts cost: about $113 (camera, servos, mount, power), before the computer that runs the model. Not a validated system.',
    // The line along the bottom of the hero. Plain facts only.
    facts: ['Detection only', '~$113 est. sensing parts', 'Tested in simulation and on recorded video', 'Not yet on real hardware'],
    caption: 'SAMPLE: a placeholder sighting, not a real detection. Real sightings replace it once the hardware is built.',

    // The glass sighting card beside the lens. Placeholder values only.
    // status: 'aircraft' (confirmed aircraft), 'drone' (possible drone) or
    // 'no-adsb' (no ADS-B match). The colour and shape follow automatically.
    card: {
      label: 'SAMPLE',
      status: 'aircraft',
      time: '14:32:07Z',
      class: 'aircraft',
      conf: '0.91',
      adsb: 'match',
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

  // WHAT WE'VE TESTED: the short version, near the top. Three columns:
  // software tests, recorded-video results (with their limits beside them),
  // and hardware tests still pending. Keep it in step with status and results.
  tested: {
    heading: "What we've tested",
    columns: [
      {
        tag: 'DONE · SOFTWARE',
        title: 'Software tests',
        items: [
          'Detection, tracking and pan-tilt control loop, in simulation',
          'Sighting logger and live dashboard, in simulation',
          'Pico servo firmware, tested in software',
        ],
      },
      {
        tag: 'MEASURED · RECORDED VIDEO',
        title: 'Recorded-video results',
        items: [
          'Model v2 on 43 real-world clips',
          '14.9% of drone clips labeled correctly: v2 is weak at drones',
          '7.5% of aircraft frames wrongly called a drone',
        ],
      },
      {
        tag: 'PENDING · HARDWARE',
        title: 'Hardware tests',
        items: [
          'Physical node not built yet',
          'No outdoor test yet',
          'No comparison against real flight data (ADS-B) yet',
        ],
      },
    ],
    link: { label: 'Full results and limits', href: '#results' },
  },

  // The pinned scroll story. Each stage has its own animated scene in the
  // panel (see storyScene in render.js). Everything in the panel is a
  // simulation and is labelled SAMPLE.
  story: {
    kicker: 'How it works',
    heading: 'From sky to sighting',
    intro: 'Five steps turn a patch of sky into a logged record. Keep scrolling and watch one happen.',
    device: 'SAMPLE · NODE-01 · SIMULATED',
    note: 'SAMPLE: everything in this panel is a simulation, not footage.',
    stages: [
      {
        number: '01',
        title: 'SEE',
        fact: 'Passive · receives light only',
        body: 'A webcam on a pan-tilt mount looks at the sky. Varn is passive: it only receives light. It never jams, never transmits on aircraft or drone frequencies, and carries no payload.',
      },
      {
        number: '02',
        title: 'DETECT',
        fact: 'YOLO · ONNX model',
        body: 'Every frame goes through a YOLO object-detection model. For each thing it finds, it returns a class (drone or aircraft), a confidence score and a box. Today that is model v2, which is weak at drones. Model v3 is in training.',
      },
      {
        number: '03',
        title: 'TRACK',
        fact: 'Pico · two servos',
        body: 'The tracker picks one target and stays locked on it from frame to frame. A small controller turns how far off-centre the target is into new pan and tilt angles, and a Raspberry Pi Pico drives the two servos.',
      },
      {
        number: '04',
        title: 'LOG',
        fact: 'Time · class · confidence · direction',
        body: 'Every sighting is saved with its time, what it was, how confident the model was and which way the camera was pointing, plus a snapshot of its best moment. An hourly sky-clear check records the quiet too.',
      },
      {
        number: '05',
        title: 'CHECK',
        fact: 'ADS-B · built, not yet run on a real feed',
        body: 'Planes publicly broadcast their positions (ADS-B). Varn can line its sightings up with a log of the real flights overhead, which is how real accuracy numbers will be measured. That comparison is written but has not run against a real feed yet.',
      },
    ],
  },

  // How to read the three status labels.
  labels: {
    kicker: 'Reading the screen',
    heading: 'Three labels, three shapes',
    intro: 'Colour is never the only signal. Every label pairs a colour with a shape and a word, so it reads the same in greyscale and for colour-blind eyes.',
    items: [
      {
        kind: 'aircraft',
        title: 'Confirmed aircraft',
        shape: 'Filled circle',
        rule: 'The model sees an aircraft and a matching ADS-B broadcast is nearby.',
      },
      {
        kind: 'drone',
        title: 'Possible drone',
        shape: 'Filled square',
        rule: 'The model says drone. It is always only possible: a model can be wrong, and Varn says so.',
      },
      {
        kind: 'no-adsb',
        title: 'No ADS-B match',
        shape: 'Hollow ring',
        rule: 'Looks like an aircraft, but no matching broadcast was found. It may be a plane that does not broadcast, or a misread.',
      },
    ],
    note: 'The ADS-B comparison is written but has not yet been run against a real feed, so these labels are shown here as a design, not as measured results.',
  },

  math: {
    heading: 'The math is backwards',
    // Words inside [square brackets] light up white; the rest stay grey.
    statement: 'A small drone costs [a few hundred dollars.] Systems built to detect one cost [tens of thousands.]',
    stats: [
      { label: 'A small drone', value: '$100s' },
      { label: 'Typical detection system', value: '$10,000s' },
      { label: 'Estimated Varn sensing-hardware parts (excludes the computer)', value: '~$113', highlight: true },
    ],
    // Printed under the numbers so they can't be read as a capability claim.
    statsNote: 'Price comparison only, not a capability comparison. Varn is one passive camera node and has not run on real hardware yet.',
    body: 'Varn is a first step toward making that sensing layer cheap enough to put anywhere.',
    useCases: {
      tag: 'USE CASES',
      text: `Early use cases I'm exploring: farms, small airports, stadiums, and power substations. First hypothesis to test: small general-aviation airfields.`,
    },
  },

  how: {
    kicker: 'Under the hood',
    heading: 'The hardware and the view',
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
      label: 'SAMPLE · SENSOR VIEW · SIMULATED',
      caption:
        'SAMPLE: a simulation of the overlay the node draws on its camera feed (brain/overlay.py). The locked target gets the bold box and a solid label; anything else gets a thin box. The camera turns to keep the lock in the centre ring.',
    },
    // Simulated radar sweep beside the sensor view (radar.js). Must say SAMPLE.
    radar: {
      label: 'SAMPLE · SKY PICTURE · SIMULATED',
      caption:
        'SAMPLE: made-up blips showing how sightings could be plotted around the node. Circle = aircraft, square = possible drone. Varn has no radar; this is a map of what the camera reports.',
    },
    note: 'The test range is free: real air traffic passes overhead all day. Planes publicly broadcast their positions (ADS-B), so I can compare what the camera saw with what actually flew over and report real accuracy numbers.',
  },

  status: {
    kicker: 'Where it stands',
    heading: 'Status',
    items: [
      { label: 'DONE', text: 'Pico servo firmware: smooth motion, calibration, command protocol' },
      { label: 'DONE', text: 'Detection and tracking loop, working in simulation, 243 automated tests' },
      { label: 'DONE', text: 'Pan-tilt mount designed in CAD, with STEP and STL files' },
      { label: 'DONE', text: 'Wiring diagram and bill of materials' },
      { label: 'DONE', text: 'Sighting logger (built and tested in simulation)' },
      { label: 'DONE', text: 'Live dashboard (built and tested in simulation)' },
      { label: 'IN PROGRESS', text: 'Detection model v3 with drone and aircraft classes (in training)' },
      { label: 'NEXT', text: 'Run the logger and dashboard on real hardware' },
      { label: 'NEXT', text: 'Build the physical hardware' },
      { label: 'NEXT', text: 'Outdoor test' },
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
      { value: '14.9%', label: 'Drone clips labeled correctly', note: 'v2 is weak at drones. v3 is training to fix this.' },
      { value: '0.8%', label: 'Civilian planes called drones' },
      { value: '10.8%', label: 'Military jets called drones', note: 'Mostly distant F-35s' },
    ],
    source: 'Model v2, 43 real-world videos. v3 (drone and aircraft classes, 960 px input) is in training. There are no v3 results yet.',
  },

  // KNOWN LIMITS: what Varn can't do, stated plainly.
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
    body: `I'm Braden, and I like building things that work in the real world. I started with Sunnode, a small server that runs entirely on solar power from a panel on my fence. Then I got curious about drones, trained my first detection model, and Varn was the next step. I've run a backyard gardening business, and I shelved a software startup after learning how hard it is to sell to companies when you're young. I'm interested in how technology can make shared airspace safer, and Varn is where I'm starting.`,
  },

  roadmap: {
    kicker: 'Roadmap',
    heading: 'From one node to a network',
    // The long-term vision lives here, not in the hero.
    intro: 'This is Phase 1. The long-term goal is affordable, passive airspace awareness: knowing what is flying overhead, openly measured and documented.',
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
        title: 'Wider awareness',
        body: 'Low-cost passive sensing for places that need to know what is in their airspace, like small airfields, with published accuracy at every step.',
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
    brand: 'VARN LABS',
    links: [
      { label: 'Varn on GitHub', href: 'https://github.com/bsalsa2/varn' },
      { label: 'Sister project: Sunnode', href: 'https://github.com/bsalsa2/sunnode' },
      { label: 'Privacy', href: './privacy.html' },
    ],
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
