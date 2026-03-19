#!/usr/bin/env node
/**
 * App Icon Generator for AutoRename-PDF
 *
 * Adapted from electron-workspace's shared icon generator.
 * Generates consistent app icons from an SVG definition in icons.config.json.
 *
 * Usage:
 *   node scripts/generate-app-icons.cjs --config icons.config.json
 *
 * Outputs: PNG (multiple sizes), ICO (Windows), ICNS (macOS)
 */

const fs = require('fs')
const path = require('path')

// Check for sharp
let sharp
try {
  sharp = require('sharp')
} catch (e) {
  console.error('Missing dependency: sharp')
  console.error('Run: pnpm add -D sharp')
  process.exit(1)
}

// Check for png2icons (creates proper multi-size ICO and ICNS)
let png2icons
try {
  png2icons = require('png2icons')
} catch (e) {
  console.error('Missing dependency: png2icons')
  console.error('Run: pnpm add -D png2icons')
  process.exit(1)
}

// Standard sizes (includes Windows DPI scaling sizes)
const SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024]

// Standard visual parameters
const CANVAS_SIZE = 1024
const CORNER_RADIUS = 200
const ICON_SCALE = 28
const TRAY_CANVAS_SIZE = 256
const TRAY_CORNER_RADIUS = 50
const TRAY_SCALE = 7

/**
 * Generate path attributes based on fill vs stroke mode
 */
function getPathAttrs(strokeWidth) {
  if (strokeWidth) {
    return `fill="none" stroke="white" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round"`
  }
  return `fill-rule="evenodd" fill="white"`
}

/**
 * Generate the main app icon SVG
 */
function generateIconSvg(config) {
  const { colors, iconPath, iconContent, iconCenter = { x: 12, y: 12 }, strokeWidth } = config

  const translateX = (CANVAS_SIZE / 2) - (iconCenter.x * ICON_SCALE)
  const translateY = (CANVAS_SIZE / 2) - (iconCenter.y * ICON_SCALE)

  let iconElement
  if (iconContent) {
    iconElement = iconContent
  } else {
    const pathAttrs = getPathAttrs(strokeWidth)
    iconElement = `<path d="${iconPath}" ${pathAttrs}/>`
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${CANVAS_SIZE}" height="${CANVAS_SIZE}" viewBox="0 0 ${CANVAS_SIZE} ${CANVAS_SIZE}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${colors.start}"/>
      <stop offset="100%" style="stop-color:${colors.end}"/>
    </linearGradient>
  </defs>

  <!-- Background with rounded corners and gradient -->
  <rect width="${CANVAS_SIZE}" height="${CANVAS_SIZE}" rx="${CORNER_RADIUS}" fill="url(#bgGradient)"/>

  <!-- App icon - centered -->
  <g transform="translate(${translateX}, ${translateY}) scale(${ICON_SCALE})">
    ${iconElement}
  </g>
</svg>`
}

/**
 * Generate the tray icon SVG
 */
function generateTraySvg(config) {
  const { colors, iconPath, iconContent, iconCenter = { x: 12, y: 12 }, strokeWidth } = config

  const translateX = (TRAY_CANVAS_SIZE / 2) - (iconCenter.x * TRAY_SCALE)
  const translateY = (TRAY_CANVAS_SIZE / 2) - (iconCenter.y * TRAY_SCALE)

  let iconElement
  if (iconContent) {
    iconElement = iconContent
  } else {
    const trayStrokeWidth = strokeWidth ? strokeWidth * (TRAY_SCALE / ICON_SCALE) : null
    const pathAttrs = getPathAttrs(trayStrokeWidth)
    iconElement = `<path d="${iconPath}" ${pathAttrs}/>`
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${TRAY_CANVAS_SIZE}" height="${TRAY_CANVAS_SIZE}" viewBox="0 0 ${TRAY_CANVAS_SIZE} ${TRAY_CANVAS_SIZE}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="trayBgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${colors.start}"/>
      <stop offset="100%" style="stop-color:${colors.end}"/>
    </linearGradient>
  </defs>

  <!-- Background with rounded corners -->
  <rect width="${TRAY_CANVAS_SIZE}" height="${TRAY_CANVAS_SIZE}" rx="${TRAY_CORNER_RADIUS}" fill="url(#trayBgGradient)"/>

  <!-- App icon - centered -->
  <g transform="translate(${translateX}, ${translateY}) scale(${TRAY_SCALE})">
    ${iconElement}
  </g>
</svg>`
}

/**
 * Generate all icons for the app
 */
async function generateIcons(config) {
  const { appName, outputDir, colors, iconPath, iconContent, iconCenter, strokeWidth, generateTray = true } = config

  console.log(`Generating ${appName} app icons...\n`)

  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true })
  }

  const iconSvg = generateIconSvg({ colors, iconPath, iconContent, iconCenter, strokeWidth })
  const traySvg = generateTray ? generateTraySvg({ colors, iconPath, iconContent, iconCenter, strokeWidth }) : null

  // Save source SVG
  const svgPath = path.join(outputDir, 'icon-source.svg')
  fs.writeFileSync(svgPath, iconSvg)
  console.log('Created: icon-source.svg')

  if (traySvg) {
    const traySvgPath = path.join(outputDir, 'tray-source.svg')
    fs.writeFileSync(traySvgPath, traySvg)
    console.log('Created: tray-source.svg')
  }

  // Generate PNG icons at various sizes
  console.log('\nGenerating PNG icons...')
  for (const size of SIZES) {
    const filename = size === 1024 ? 'icon.png' : `icon_${size}x${size}.png`
    const outputPath = path.join(outputDir, filename)

    await sharp(Buffer.from(iconSvg))
      .resize(size, size)
      .png()
      .toFile(outputPath)

    console.log(`  + ${filename}`)
  }

  // Tauri-specific named PNGs (symlinks/copies for Tauri's expected filenames)
  console.log('\nGenerating Tauri-specific PNGs...')
  const tauriSizes = [
    { src: 'icon_32x32.png', dst: '32x32.png' },
    { src: 'icon_128x128.png', dst: '128x128.png' },
    { src: 'icon_256x256.png', dst: '128x128@2x.png' },
  ]
  for (const { src, dst } of tauriSizes) {
    fs.copyFileSync(path.join(outputDir, src), path.join(outputDir, dst))
    console.log(`  + ${dst} (from ${src})`)
  }

  // Generate tray icons
  if (traySvg) {
    console.log('\nGenerating tray icons...')
    await sharp(Buffer.from(traySvg))
      .resize(16, 16)
      .png()
      .toFile(path.join(outputDir, 'tray-icon.png'))
    console.log('  + tray-icon.png (16x16)')

    await sharp(Buffer.from(traySvg))
      .resize(32, 32)
      .png()
      .toFile(path.join(outputDir, 'tray-icon@2x.png'))
    console.log('  + tray-icon@2x.png (32x32)')
  }

  // Generate Windows .ico
  // png2icons creates ICO with sizes: 16, 24, 32, 48, 64, 72, 96, 128, 256
  const iconPngPath = path.join(outputDir, 'icon.png')
  const iconPngBuffer = fs.readFileSync(iconPngPath)

  console.log('\nGenerating Windows .ico (16, 24, 32, 48, 64, 72, 96, 128, 256px)...')
  try {
    const icoBuffer = png2icons.createICO(iconPngBuffer, png2icons.BICUBIC, 0, true, true)
    if (icoBuffer) {
      fs.writeFileSync(path.join(outputDir, 'icon.ico'), icoBuffer)
      console.log('  + icon.ico')
    } else {
      console.log('  ! Failed to create icon.ico')
    }
  } catch (e) {
    console.log('  ! Could not generate .ico:', e.message)
  }

  // Generate tray.ico from tray PNG
  if (traySvg) {
    console.log('\nGenerating tray.ico...')
    try {
      const trayPngPath = path.join(outputDir, 'tray-icon@2x.png')
      const trayPngBuffer = fs.readFileSync(trayPngPath)
      const trayIcoBuffer = png2icons.createICO(trayPngBuffer, png2icons.BICUBIC, 0, true, true)
      if (trayIcoBuffer) {
        fs.writeFileSync(path.join(outputDir, 'tray.ico'), trayIcoBuffer)
        console.log('  + tray.ico')
      } else {
        console.log('  ! Failed to create tray.ico')
      }
    } catch (e) {
      console.error('  ! Failed to create tray.ico:', e.message)
    }
  }

  // Generate macOS .icns
  console.log('\nGenerating macOS .icns...')
  try {
    const icnsBuffer = png2icons.createICNS(iconPngBuffer, png2icons.BICUBIC, 0)
    if (icnsBuffer) {
      fs.writeFileSync(path.join(outputDir, 'icon.icns'), icnsBuffer)
      console.log('  + icon.icns')
    } else {
      console.log('  ! Failed to create icon.icns')
    }
  } catch (e) {
    console.log('  ! Could not generate .icns:', e.message)
  }

  console.log(`\nIcon generation complete!`)
  console.log(`Output directory: ${outputDir}`)
}

// CLI support
if (require.main === module) {
  const args = process.argv.slice(2)
  const configIndex = args.indexOf('--config')

  if (configIndex === -1 || !args[configIndex + 1]) {
    console.error('Usage: generate-app-icons.cjs --config <config.json>')
    process.exit(1)
  }

  const configPath = path.resolve(args[configIndex + 1])
  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))

  // Resolve outputDir relative to config file
  if (config.outputDir && !path.isAbsolute(config.outputDir)) {
    config.outputDir = path.resolve(path.dirname(configPath), config.outputDir)
  }

  generateIcons(config).catch(console.error)
}

module.exports = { generateIcons, generateIconSvg, generateTraySvg }
