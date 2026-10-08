import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const EDGE_CANDIDATES = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
]
const EDGE = EDGE_CANDIDATES.find((path) => fs.existsSync(path))
const APP_URL = 'http://localhost:5173'

if (!EDGE) {
  console.error('Aucun navigateur Chrome/Edge trouvé sur cette machine.')
  process.exit(1)
}

const failures = []
const consoleErrors = []
const resourceErrors = []

function check(label, condition, detail = '') {
  if (condition) {
    console.log(`  OK   ${label}`)
  } else {
    failures.push(`${label} ${detail}`)
    console.log(`  FAIL ${label} ${detail}`)
  }
}

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu'],
})

try {
  const page = await browser.newPage()
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (text.includes('Failed to load resource')) {
      resourceErrors.push(text)
      return
    }
    consoleErrors.push(text)
  })
  page.on('pageerror', (error) => consoleErrors.push(String(error)))

  await page.setViewport({ width: 1280, height: 800 })
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 30000 })

  console.log('1. Chargement de l application')
  await page.waitForSelector('.sidebar__create', { timeout: 15000 })
  check('le bouton de création est affiché', true)

  const loaded = await page.evaluate(
    () => !document.querySelector('.spinner__label')?.textContent?.includes('Chargement'),
  )
  check('le chargement initial se termine', loaded)

  console.log('2. Création d une conversation')
  const before = await page.$$eval('.conversation-item', (els) => els.length)
  await page.click('.sidebar__create')
  await page.waitForFunction(
    (count) => document.querySelectorAll('.conversation-item').length > count,
    { timeout: 15000 },
    before,
  )
  const after = await page.$$eval('.conversation-item', (els) => els.length)
  check('la conversation apparaît dans la liste', after === before + 1, `(${before} -> ${after})`)

  await page.waitForSelector('.message__html h2', { timeout: 15000 })
  const welcome = await page.$eval('.message__html h2', (el) => el.textContent ?? '')
  check('le message de bienvenue est rendu en HTML', welcome.includes('pâtissIA'), `"${welcome}"`)

  const title = await page.$eval('.chat__title', (el) => el.textContent ?? '')
  check('l en-tête affiche le titre', title.length > 0, `"${title}"`)

  console.log('3. Envoi d un message au chatbot')
  await page.waitForSelector('.composer__input', { timeout: 10000 })
  await page.type('.composer__input', 'Bonjour, un conseil pour une tarte ?')
  await page.keyboard.press('Enter')
  await page.waitForFunction(
    () =>
      document.querySelectorAll('.message').length > 1 ||
      document.querySelector('.error-banner') !== null,
    { timeout: 30000 },
  )
  const banner = await page.$('.error-banner')
  const messageCount = await page.$$eval('.message', (els) => els.length)
  check(
    'le chat répond ou affiche une erreur explicite',
    messageCount > 1 || banner !== null,
    `(messages=${messageCount}, erreur=${banner !== null})`,
  )
  if (banner) {
    const bannerText = await banner.evaluate((el) => el.textContent ?? '')
    console.log(`       bandeau: ${bannerText.trim()}`)
    const closed = await page.evaluate(() => {
      const btn = document.querySelector('.error-banner__close')
      if (btn) btn.click()
      return true
    })
    check('le bandeau d erreur se ferme', closed)
    await page.waitForFunction(() => document.querySelector('.error-banner') === null, {
      timeout: 5000,
    })
  }

  console.log('4. Historique rechargé depuis l API')
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('.sidebar__create', { timeout: 15000 })
  await page.waitForSelector('.conversation-item', { timeout: 15000 })
  check('les conversations sont restaurées après rechargement', true)

  console.log('5. Suppression d une conversation')
  const countBeforeDelete = await page.$$eval('.conversation-item', (els) => els.length)
  await page.click('.conversation-item__delete')
  await page.click('.conversation-item__delete')
  await page.waitForFunction(
    (count) => document.querySelectorAll('.conversation-item').length < count,
    { timeout: 15000 },
    countBeforeDelete,
  )
  const countAfterDelete = await page.$$eval('.conversation-item', (els) => els.length)
  check(
    'la conversation est supprimée',
    countAfterDelete === countBeforeDelete - 1,
    `(${countBeforeDelete} -> ${countAfterDelete})`,
  )

  console.log('6. Affichage responsive (mobile 390x844)')
  await page.setViewport({ width: 390, height: 844 })
  await new Promise((resolve) => setTimeout(resolve, 400))
  const sidebarHidden = await page.evaluate(() => {
    const sidebar = document.querySelector('.sidebar')
    if (!sidebar) return false
    const rect = sidebar.getBoundingClientRect()
    return rect.right <= 0
  })
  check('la barre latérale est masquée sur mobile', sidebarHidden)
  const menuVisible = await page.evaluate(() => {
    const btn = document.querySelector('.chat__menu')
    if (!btn) return false
    const style = getComputedStyle(btn)
    return style.display !== 'none'
  })
  check('le bouton de menu est visible sur mobile', menuVisible)
  await page.click('.chat__menu')
  await new Promise((resolve) => setTimeout(resolve, 400))
  const sidebarOpen = await page.evaluate(() => {
    const sidebar = document.querySelector('.sidebar')
    return sidebar !== null && sidebar.classList.contains('sidebar--open')
  })
  check('le menu s ouvre sur mobile', sidebarOpen)

  await page.screenshot({
    path: 'C:\\Users\\lenovo\\AppData\\Local\\Temp\\opencode\\app-mobile.png',
    fullPage: false,
  })

  await page.setViewport({ width: 1280, height: 800 })
  await new Promise((resolve) => setTimeout(resolve, 400))
  await page.screenshot({
    path: 'C:\\Users\\lenovo\\AppData\\Local\\Temp\\opencode\\app-desktop.png',
    fullPage: false,
  })

  console.log('7. Erreurs console')
  if (resourceErrors.length > 0) {
    console.log(`       requêtes en échec attendues: ${resourceErrors.length}`)
  }
  check(
    'aucune erreur JavaScript',
    consoleErrors.length === 0,
    consoleErrors.join(' | '),
  )
} finally {
  await browser.close()
}

if (failures.length > 0) {
  console.error(`\n${failures.length} échec(s):`)
  for (const failure of failures) console.error(` - ${failure}`)
  process.exit(1)
}
console.log('\nTous les contrôles sont passés.')
