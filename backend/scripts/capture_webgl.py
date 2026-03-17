#!/usr/bin/env python3
"""Capture real WebGL parameters from the system GPU via Playwright + Firefox.

Collects the same parameter set that Camoufox's webgl_data.db stores:
- webGl:vendor, webGl:renderer
- webGl:parameters (147 GL constants)
- webGl:supportedExtensions
- webGl:contextAttributes
- webGl:shaderPrecisionFormats
- Same for WebGL 2.0

Output: JSON file compatible with webgl_data.db `data` column format.

Usage:
    python scripts/capture_webgl.py [--output captured_webgl.json]

Requirements:
    pip install playwright
    playwright install firefox
"""

import argparse
import asyncio
import json
import sys

# All GL parameter constants to query (from Camoufox webgl_data.db schema)
PNAMES = [
    2849, 2884, 2885, 2886, 2928, 2929, 2930, 2931, 2932,
    2960, 2961, 2962, 2963, 2964, 2965, 2966, 2967, 2968,
    2978, 3024, 3042, 3074, 3088, 3089, 3106, 3107,
    3314, 3315, 3316, 3317, 3330, 3331, 3332, 3333,
    3379, 3386, 3408, 3410, 3411, 3412, 3413, 3414, 3415,
    7936, 7937, 7938, 10752,
    32773, 32777, 32823, 32824, 32873, 32877, 32878, 32883,
    32926, 32928, 32936, 32937, 32938, 32939,
    32968, 32969, 32970, 32971, 33000, 33001, 33170,
    33901, 33902, 34016, 34024, 34045, 34047, 34068, 34076,
    34467, 34816, 34817, 34818, 34819,
    34852, 34853, 34854, 34855, 34856, 34857, 34858, 34859, 34860,
    34877, 34921, 34930, 34964, 34965,
    35071, 35076, 35077,
    35371, 35373, 35374, 35375, 35376, 35377, 35379, 35380,
    35657, 35658, 35659, 35660, 35661,
    35723, 35724, 35725, 35738, 35739,
    35968, 35977, 35978, 35979,
    36003, 36004, 36005, 36006, 36007,
    36063, 36183, 36203, 36345, 36347, 36348, 36349,
    36387, 36388, 36392, 36795,
    37137, 37154, 37157,
    37440, 37441, 37443, 37444, 37445, 37446, 37447,
    38449,
]

# Shader precision format keys: (shaderType, precisionType)
# 35632 = FRAGMENT_SHADER, 35633 = VERTEX_SHADER
# 36336 = LOW_FLOAT, 36337 = MEDIUM_FLOAT, 36338 = HIGH_FLOAT
# 36339 = LOW_INT, 36340 = MEDIUM_INT, 36341 = HIGH_INT
SHADER_PRECISION_KEYS = [
    (35632, 36336), (35632, 36337), (35632, 36338),
    (35632, 36339), (35632, 36340), (35632, 36341),
    (35633, 36336), (35633, 36337), (35633, 36338),
    (35633, 36339), (35633, 36340), (35633, 36341),
]

# JavaScript to collect ALL WebGL data from the real GPU
CAPTURE_JS = """
() => {
    function serializeValue(val) {
        if (val === null || val === undefined) return null;
        if (typeof val === 'boolean' || typeof val === 'number' || typeof val === 'string') return val;
        if (val instanceof Float32Array || val instanceof Int32Array || val instanceof Uint32Array) {
            return Array.from(val);
        }
        if (Array.isArray(val)) return val;
        return null;
    }

    function collectParams(gl, pnames) {
        const params = {};
        for (const pname of pnames) {
            try {
                const val = gl.getParameter(pname);
                params[String(pname)] = serializeValue(val);
            } catch (e) {
                params[String(pname)] = null;
            }
        }
        return params;
    }

    function collectShaderPrecision(gl, keys) {
        const formats = {};
        for (const [shaderType, precisionType] of keys) {
            try {
                const fmt = gl.getShaderPrecisionFormat(shaderType, precisionType);
                if (fmt) {
                    formats[shaderType + ',' + precisionType] = {
                        rangeMin: fmt.rangeMin,
                        rangeMax: fmt.rangeMax,
                        precision: fmt.precision,
                    };
                }
            } catch (e) {}
        }
        return formats;
    }

    function collectContextAttribs(gl) {
        const attribs = gl.getContextAttributes();
        if (!attribs) return {};
        return {
            alpha: attribs.alpha,
            antialias: attribs.antialias,
            depth: attribs.depth,
            failIfMajorPerformanceCaveat: attribs.failIfMajorPerformanceCaveat,
            powerPreference: attribs.powerPreference,
            premultipliedAlpha: attribs.premultipliedAlpha,
            preserveDrawingBuffer: attribs.preserveDrawingBuffer,
            stencil: attribs.stencil,
        };
    }

    const pnames = PNAMES_PLACEHOLDER;
    const shaderKeys = SHADER_KEYS_PLACEHOLDER;
    const result = {};

    // WebGL 1.0
    const canvas1 = document.createElement('canvas');
    const gl1 = canvas1.getContext('webgl');
    if (!gl1) return { error: 'WebGL 1.0 not supported' };

    const debugInfo = gl1.getExtension('WEBGL_debug_renderer_info');

    result['webGl:vendor'] = debugInfo
        ? gl1.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL)
        : gl1.getParameter(gl1.VENDOR);
    result['webGl:renderer'] = debugInfo
        ? gl1.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)
        : gl1.getParameter(gl1.RENDERER);

    result['webGl:parameters'] = collectParams(gl1, pnames);
    result['webGl:supportedExtensions'] = gl1.getSupportedExtensions() || [];
    result['webGl:contextAttributes'] = collectContextAttribs(gl1);
    result['webGl:shaderPrecisionFormats'] = collectShaderPrecision(gl1, shaderKeys);

    // WebGL 2.0
    const canvas2 = document.createElement('canvas');
    const gl2 = canvas2.getContext('webgl2');
    if (gl2) {
        result['webGl2Enabled'] = true;
        result['webGl2:parameters'] = collectParams(gl2, pnames);
        result['webGl2:supportedExtensions'] = gl2.getSupportedExtensions() || [];
        result['webGl2:contextAttributes'] = collectContextAttribs(gl2);
        result['webGl2:shaderPrecisionFormats'] = collectShaderPrecision(gl2, shaderKeys);
    } else {
        result['webGl2Enabled'] = false;
    }

    return result;
}
"""


async def capture_webgl(output_path: str) -> dict:
    """Launch system Firefox, capture real WebGL parameters, return as dict."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install firefox")
        sys.exit(1)

    # Inject pnames and shader keys into JS
    js_code = CAPTURE_JS.replace(
        "PNAMES_PLACEHOLDER", json.dumps(PNAMES)
    ).replace(
        "SHADER_KEYS_PLACEHOLDER", json.dumps(SHADER_PRECISION_KEYS)
    )

    async with async_playwright() as p:
        # Use system Firefox to get real GPU values (Playwright's bundled
        # Firefox masks WebGL renderer even with RFP disabled).
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",  # Use system Google Chrome
        )
        page = await browser.new_page()
        await page.goto("https://www.example.com", wait_until="domcontentloaded")
        result = await page.evaluate(f"({js_code})()")
        await browser.close()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    # Print summary
    vendor = result.get("webGl:vendor", "?")
    renderer = result.get("webGl:renderer", "?")
    params_count = len(result.get("webGl:parameters", {}))
    ext_count = len(result.get("webGl:supportedExtensions", []))
    webgl2 = result.get("webGl2Enabled", False)

    print(f"Captured WebGL from real GPU:")
    print(f"  Vendor:     {vendor}")
    print(f"  Renderer:   {renderer}")
    print(f"  Parameters: {params_count}")
    print(f"  Extensions: {ext_count}")
    print(f"  WebGL2:     {webgl2}")
    if webgl2:
        print(f"  WebGL2 params: {len(result.get('webGl2:parameters', {}))}")
        print(f"  WebGL2 exts:   {len(result.get('webGl2:supportedExtensions', []))}")

    # Save to file
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to: {output_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture real WebGL parameters from system GPU")
    parser.add_argument("--output", "-o", default="captured_webgl.json", help="Output JSON file")
    args = parser.parse_args()
    asyncio.run(capture_webgl(args.output))
