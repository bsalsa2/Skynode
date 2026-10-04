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
      'Skynode is a camera that detects and tracks aircraft and drones, built to cost hundreds of dollars instead of tens of thousands.',
    // Public URL of the live site (used for social share previews).
    url: 'https://skynode-si.netlify.app/',
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
    eyebrow: 'PHASE 1: AI SKY TRACKER',
    headline: `Drones are cheap. Detecting them isn't.`,
    sub: 'Skynode is a camera that detects and tracks aircraft and drones, built to cost hundreds of dollars instead of tens of thousands. It turns to follow what it sees and logs every sighting.',
    primary: { label: 'View the code', href: 'https://github.com/bsalsa2/skynode' },
    secondary: { label: 'See where it stands', href: '#status' },
    // Shown under the buttons.
    goal: 'This is Phase 1. The long-term goal is autonomy for missile and drone defense and attack systems.',
    facts: ['Passive sensing only', 'Designed for solar power', 'MIT licensed'],
    caption:
      'Concept visualization. Live footage will replace this once the hardware is built.',

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
    body: 'A small drone costs a few hundred dollars. Systems built to detect one cost tens of thousands. So most farms, small airports, stadiums, and power substations have no way to know when something is overhead. Skynode is a first step toward making that sensing layer cheap enough to put anywhere.',
  },

  how: {
    heading: 'How it works',
    steps: [
      {
        number: '01',
        title: 'SENSE',
        body: 'A YOLO object-detection model looks at the camera feed and picks out aircraft and drones. It is training now on a dataset of 28,526 labeled images.',
      },
      {
        number: '02',
        title: 'TRACK',
        body: 'A Raspberry Pi Pico drives two small servos on a pan-tilt mount, turning the camera to keep the target centered.',
      },
      {
        number: '03',
        title: 'LOG',
        body: 'Every sighting is saved with the time, what it was, how confident the model was, and which way the camera was pointing.',
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
    note: 'The test range is free: real air traffic passes overhead all day. Planes publicly broadcast their positions (ADS-B), so I can compare what the camera saw with what actually flew over and report real accuracy numbers.',
  },

  status: {
    heading: 'Status',
    items: [
      { label: 'DONE', text: 'Pico servo firmware: smooth motion, calibration, command protocol' },
      { label: 'DONE', text: 'Detect, track, and aim loop, working in simulation, 70 automated tests' },
      { label: 'DONE', text: 'Pan-tilt mount designed in CAD, with STEP and STL files' },
      { label: 'DONE', text: 'Wiring diagram and bill of materials' },
      { label: 'IN PROGRESS', text: 'Training the detection model on 28,526 images' },
      { label: 'NEXT', text: 'Build the physical hardware. Nothing has run on real hardware yet.' },
      { label: 'NEXT', text: 'Test against real flight data (ADS-B) and publish accuracy results' },
      { label: 'NEXT', text: 'Run it outdoors on solar power' },
    ],
  },

  // ACCURACY RESULTS: this section stays hidden until items has entries.
  // Only add numbers you have actually measured, and fill in source with how
  // and when they were measured. The build refuses numbers without a source.
  results: {
    heading: 'Results',
    intro: '',
    items: [
      // { value: '00%', label: 'What was measured', note: 'Optional detail' },
    ],
    source: '',
  },

  build: {
    heading: 'About me',
    body: `I'm Braden, I'm 14, and I like building things that work in the real world. I started with Sunnode, a small server that runs entirely on solar power from a panel on my fence. Then I got curious about drones, trained my first detection model, and Skynode was the next step. I've run a backyard gardening business, and I shelved a software startup after learning how hard it is to sell to companies when you're 13. I'm fascinated by geopolitics and technology, and I want to build an aerospace and defense company someday. Skynode is where I'm starting.`,
    // Personal quote, shown under the text and signed with your first name.
    quote: 'You only live once so go out there and make the most of every moment by chasing your dreams and living without regret',
    signature: 'Braden',
  },

  roadmap: {
    heading: 'Roadmap',
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
        body: 'For inspection, search and rescue, and drone defense and attack systems, built on the same sensing and tracking brain.',
      },
      {
        phase: 'PHASE 4',
        title: 'A company',
        body: `An aerospace and defense company building autonomy for missile and drone defense and attack systems, once I'm old enough to start one.`,
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
    sections: [
      {
        heading: 'What the site loads',
        text: 'Everything on this site, including the fonts, scripts, and 3D models, is served from the site itself. Your browser makes no requests to other companies while you read it.',
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
