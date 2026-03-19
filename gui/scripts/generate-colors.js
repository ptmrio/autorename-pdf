#!/usr/bin/env node
/**
 * Unified Color Generator for AutoRename-PDF GUI
 *
 * Generates accessible, perceptually uniform color palettes using OKLCH color science.
 * Outputs either CSS @theme blocks (Tailwind v4) or JS modules (Tailwind v3).
 *
 * Usage:
 *   node generate-colors.js --config colors.json --output generated-colors.css
 *   node generate-colors.js --primary "#10b981" --format css
 *   node generate-colors.js --config colors.json --format js
 *
 * Features:
 *   - OKLCH color science for perceptually uniform scales
 *   - sRGB gamut clamping (colors stay displayable)
 *   - WCAG AA accessibility validation (4.5:1 contrast)
 *   - Supports any CSS color format (hex, hsl, rgb, oklch)
 *   - Outputs CSS @theme blocks or JS modules
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// =============================================================================
// CULORI IMPORT
// =============================================================================

let culori
try {
  culori = await import('culori')
} catch (e) {
  console.error('Error: culori package not found.')
  console.error('Please install it: pnpm add -D culori')
  process.exit(1)
}

const { formatHex, parse, converter, wcagContrast, displayable } = culori
const toOklch = converter('oklch')
const toRgb = converter('rgb')

// =============================================================================
// CONFIGURATION
// =============================================================================

/**
 * Lightness values for Tailwind scale (50-950)
 * Optimized for:
 * - 500: White text contrast >= 4.5:1 (WCAG AA)
 * - Smooth perceptual progression
 * - Visible hover/active state differences
 */
const LIGHTNESS_SCALE = {
  50: 0.97,
  100: 0.93,
  200: 0.87,
  300: 0.78,
  400: 0.68,
  500: 0.55,  // Base - ensures white text WCAG AA
  600: 0.48,  // Hover
  700: 0.40,  // Active/pressed
  800: 0.32,
  900: 0.24,
  950: 0.15,
}

/**
 * Lightness scale for colors that use dark text (e.g., warning/yellow)
 * 500 shade is brighter to ensure dark text contrast
 */
const LIGHTNESS_SCALE_DARK_TEXT = {
  50: 0.98,
  100: 0.95,
  200: 0.90,
  300: 0.85,
  400: 0.80,
  500: 0.75,  // Brighter - ensures dark text WCAG AA
  600: 0.68,  // Hover
  700: 0.58,  // Active/pressed
  800: 0.45,
  900: 0.32,
  950: 0.20,
}

/**
 * Default base colors (used when no config provided)
 */
const DEFAULT_COLORS = {
  primary: '#3b82f6',
  secondary: '#6b7280',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  info: '#06b6d4',
}

/**
 * Colors that should use dark text instead of white on 500 shade
 */
const DARK_TEXT_COLORS = ['warning', 'light']

// =============================================================================
// COLOR PARSING & VALIDATION
// =============================================================================

/**
 * Parse any color format and return normalized OKLCH
 * Supports: hex, rgb, hsl, oklch, named colors
 */
function parseAndNormalizeColor(colorInput, colorName = 'color') {
  if (!colorInput || typeof colorInput !== 'string') {
    console.warn(`  Warning: Invalid ${colorName}: empty or not a string, skipping`)
    return null
  }

  const trimmed = colorInput.trim()
  let parsed = parse(trimmed)

  if (!parsed) {
    // Try adding # for hex without it
    if (/^[0-9a-fA-F]{3,8}$/.test(trimmed)) {
      parsed = parse('#' + trimmed)
      if (parsed) {
        console.log(`  Info: ${colorName}: Added missing # to hex color`)
      }
    }
  }

  if (!parsed) {
    console.warn(`  Warning: ${colorName}: Could not parse "${trimmed}", skipping`)
    return null
  }

  const oklch = toOklch(parsed)

  if (!oklch) {
    console.warn(`  Warning: ${colorName}: Could not convert to OKLCH, skipping`)
    return null
  }

  // Normalize and clamp values
  return {
    l: Math.max(0, Math.min(1, oklch.l || 0.5)),
    c: Math.max(0, Math.min(0.4, oklch.c || 0.15)),
    h: ((oklch.h || 0) % 360 + 360) % 360,
  }
}

// =============================================================================
// COLOR GENERATION
// =============================================================================

/**
 * Taper chroma at light/dark extremes to stay in sRGB gamut
 */
function adjustChroma(baseChroma, lightness) {
  if (lightness > 0.9) return baseChroma * 0.2
  if (lightness > 0.8) return baseChroma * 0.4
  if (lightness > 0.7) return baseChroma * 0.7
  if (lightness < 0.2) return baseChroma * 0.3
  if (lightness < 0.35) return baseChroma * 0.6
  return baseChroma
}

/**
 * Clamp OKLCH color to sRGB gamut by progressively reducing chroma
 */
function clampToSrgbGamut(l, c, h) {
  let chroma = c

  for (let i = 0; i < 50; i++) {
    const color = { mode: 'oklch', l, c: chroma, h }
    const rgb = toRgb(color)

    if (rgb && displayable(rgb)) {
      return { l, c: chroma, h }
    }

    chroma *= 0.95

    if (chroma < 0.001) {
      return { l, c: 0, h }
    }
  }

  return { l, c: 0, h }
}

/**
 * Generate a full color scale from an input color
 */
function generateColorScale(inputColor, colorName = 'color') {
  const normalized = parseAndNormalizeColor(inputColor, colorName)

  if (!normalized) {
    return null
  }

  const { h: baseHue, c: baseChroma } = normalized
  const scale = {}

  const usesDarkText = DARK_TEXT_COLORS.includes(colorName)
  const lightnessScale = usesDarkText ? LIGHTNESS_SCALE_DARK_TEXT : LIGHTNESS_SCALE

  for (const [step, lightness] of Object.entries(lightnessScale)) {
    const adjustedChroma = adjustChroma(baseChroma, lightness)
    const clamped = clampToSrgbGamut(lightness, adjustedChroma, baseHue)
    const hex = formatHex({ mode: 'oklch', ...clamped })

    if (hex) {
      scale[step] = hex
    } else {
      const grayHex = formatHex({ mode: 'oklch', l: lightness, c: 0, h: 0 })
      scale[step] = grayHex || '#808080'
      console.warn(`  Warning: ${colorName}-${step}: Fell back to grayscale`)
    }
  }

  return scale
}

/**
 * Generate complete color config from base colors
 */
function generateAllColors(baseColors) {
  const result = {}
  let hasErrors = false

  for (const [name, color] of Object.entries(baseColors)) {
    const scale = generateColorScale(color, name)

    if (scale) {
      result[name] = {
        DEFAULT: scale['500'],
        ...scale,
      }
    } else {
      hasErrors = true
    }
  }

  return { colors: result, hasErrors }
}

// =============================================================================
// ACCESSIBILITY VALIDATION
// =============================================================================

/**
 * Validate generated palette for accessibility
 */
function validatePalette(colors) {
  const results = []

  for (const [name, scale] of Object.entries(colors)) {
    const bg500 = scale['500']
    const usesDarkText = DARK_TEXT_COLORS.includes(name)
    const textColor = usesDarkText ? '#1f2937' : '#ffffff'

    const bgParsed = parse(bg500)
    const fgParsed = parse(textColor)
    const contrast = bgParsed && fgParsed ? wcagContrast(bgParsed, fgParsed) : 0

    results.push({
      color: name,
      shade: 500,
      hex: bg500,
      contrast: contrast.toFixed(2),
      textColor: usesDarkText ? 'dark' : 'white',
      passes: contrast >= 4.5,
    })
  }

  return results
}

// =============================================================================
// OUTPUT FORMATTING
// =============================================================================

/**
 * Format colors as CSS @theme block (Tailwind v4)
 */
function formatAsCss(colors, inputColors) {
  const lines = [
    '/**',
    ' * Generated Color Palette - Tailwind v4',
    ' * ',
    ` * Generated: ${new Date().toISOString()}`,
    ' * Generator: generate-colors',
    ' * ',
    ' * Input colors:',
  ]

  for (const [name, color] of Object.entries(inputColors)) {
    lines.push(` *   ${name}: ${color}`)
  }

  lines.push(' * ')
  lines.push(' * Usage: @import "./generated-colors.css" in your input.css')
  lines.push(' */')
  lines.push('')
  lines.push('@theme {')

  const colorNames = Object.keys(colors)
  colorNames.forEach((name) => {
    const scale = colors[name]
    lines.push(`  /* ${name.charAt(0).toUpperCase() + name.slice(1)} */`)

    for (const [step, hex] of Object.entries(scale)) {
      if (step !== 'DEFAULT') {
        lines.push(`  --color-${name}-${step}: ${hex};`)
      }
    }
    lines.push('')
  })

  lines.push('}')
  return lines.join('\n')
}

/**
 * Format colors as JavaScript module (Tailwind v3)
 */
function formatAsJs(colors, inputColors) {
  const lines = [
    '/**',
    ' * Tailwind CSS Color Configuration',
    ' * ',
    ` * Generated: ${new Date().toISOString()}`,
    ' * Generator: generate-colors',
    ' * ',
    ' * Input colors:',
  ]

  for (const [name, color] of Object.entries(inputColors)) {
    lines.push(` *   ${name}: ${color}`)
  }

  lines.push(' * ')
  lines.push(' * Usage in tailwind.config.js:')
  lines.push(' *   const colors = require(\'./tailwind.colors.js\');')
  lines.push(' *   module.exports = { theme: { extend: { colors } } };')
  lines.push(' */')
  lines.push('')
  lines.push('module.exports = {')

  const colorNames = Object.keys(colors)
  colorNames.forEach((name, colorIndex) => {
    const scale = colors[name]
    lines.push(`  ${name}: {`)

    const entries = Object.entries(scale)
    entries.forEach(([step, hex], stepIndex) => {
      const comma = stepIndex < entries.length - 1 ? ',' : ''
      lines.push(`    ${step}: '${hex}'${comma}`)
    })

    const comma = colorIndex < colorNames.length - 1 ? ',' : ''
    lines.push(`  }${comma}`)
  })

  lines.push('};')
  return lines.join('\n')
}

// =============================================================================
// CLI
// =============================================================================

function parseArgs(args) {
  const options = {
    colors: {},
    output: null,
    format: 'css',
    validate: true,
    useDefaults: true,
  }

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]

    if (arg === '--output' || arg === '-o') {
      options.output = args[++i]
    } else if (arg === '--format' || arg === '-f') {
      const fmt = args[++i]
      if (fmt === 'css' || fmt === 'js') {
        options.format = fmt
      } else {
        console.error(`Error: Invalid format "${fmt}". Use "css" or "js".`)
        process.exit(1)
      }
    } else if (arg === '--config' || arg === '-c') {
      const configPath = args[++i]
      try {
        const fullPath = path.resolve(process.cwd(), configPath)
        const config = JSON.parse(fs.readFileSync(fullPath, 'utf8'))
        options.colors = { ...options.colors, ...config }
        options.useDefaults = false
      } catch (e) {
        console.error(`Error reading config file: ${e.message}`)
        process.exit(1)
      }
    } else if (arg === '--no-validate') {
      options.validate = false
    } else if (arg === '--no-defaults') {
      options.useDefaults = false
    } else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else if (arg.startsWith('--')) {
      // Color argument: --primary "#3b82f6"
      const colorName = arg.slice(2)
      const colorValue = args[++i]
      if (colorValue) {
        options.colors[colorName] = colorValue
        options.useDefaults = false
      }
    }
  }

  // Apply defaults if no colors specified
  if (options.useDefaults && Object.keys(options.colors).length === 0) {
    options.colors = { ...DEFAULT_COLORS }
  } else if (Object.keys(options.colors).length > 0) {
    // Merge with defaults for missing colors
    for (const [name, color] of Object.entries(DEFAULT_COLORS)) {
      if (!(name in options.colors)) {
        options.colors[name] = color
      }
    }
  }

  return options
}

function printHelp() {
  console.log(`
Color Generator for AutoRename-PDF GUI
=======================================

Generates accessible color palettes using OKLCH color science.
Outputs CSS @theme blocks (Tailwind v4) or JS modules (Tailwind v3).

Usage:
  node generate-colors.js [options]

Color Options:
  --primary <color>     Set primary color
  --secondary <color>   Set secondary color
  --success <color>     Set success color
  --danger <color>      Set danger color
  --warning <color>     Set warning color
  --info <color>        Set info color

  Colors can be: hex (#3b82f6), rgb(59,130,246), hsl(217,91%,60%), oklch(62% 0.21 255)

General Options:
  -c, --config <file>   Load colors from JSON file
  -o, --output <file>   Output file (default: stdout)
  -f, --format <fmt>    Output format: "css" (default) or "js"
  --no-validate         Skip accessibility validation
  --no-defaults         Don't include default colors for missing entries
  -h, --help            Show this help

Examples:
  # Generate CSS from config file
  node generate-colors.js --config colors.json --output generated-colors.css

  # Generate with custom primary color
  node generate-colors.js --primary "#10b981" --format css

  # Generate JS module for Tailwind v3
  node generate-colors.js --config colors.json --format js --output tailwind.colors.js

Config File Format (colors.json):
  {
    "primary": "#10b981",
    "secondary": "#6b7280",
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "info": "#06b6d4"
  }
`)
}

function printValidationResults(results) {
  const passing = results.filter(r => r.passes)
  const failing = results.filter(r => !r.passes)

  console.log('\nAccessibility Check (WCAG AA - 4.5:1 contrast):')

  for (const r of results) {
    const icon = r.passes ? '✓' : '⚠'
    const status = r.passes ? 'pass' : 'FAIL'
    console.log(`  ${icon} ${r.color}-500 (${r.hex}): ${r.contrast}:1 with ${r.textColor} text [${status}]`)
  }

  if (failing.length > 0) {
    console.log('\nNote: Failing colors may need darker base values or use dark text in components.')
  }
}

async function main() {
  const args = process.argv.slice(2)
  const options = parseArgs(args)

  console.log('Color Generator')
  console.log('===============\n')

  console.log('Input colors:')
  for (const [name, color] of Object.entries(options.colors)) {
    console.log(`  ${name}: ${color}`)
  }

  console.log('\nGenerating color scales...')

  const { colors, hasErrors } = generateAllColors(options.colors)

  if (Object.keys(colors).length === 0) {
    console.error('\nError: No valid colors generated')
    process.exit(1)
  }

  if (options.validate) {
    const results = validatePalette(colors)
    printValidationResults(results)
  }

  const output = options.format === 'css'
    ? formatAsCss(colors, options.colors)
    : formatAsJs(colors, options.colors)

  if (options.output) {
    const outputPath = path.resolve(process.cwd(), options.output)
    fs.writeFileSync(outputPath, output)
    console.log(`\n✓ Generated: ${options.output}`)
  } else {
    console.log('\n--- Output ---\n')
    console.log(output)
  }

  if (hasErrors) {
    process.exit(1)
  }
}

main().catch(err => {
  console.error('Error:', err.message)
  process.exit(1)
})
