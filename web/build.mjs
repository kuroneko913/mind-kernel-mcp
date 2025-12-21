import * as esbuild from 'esbuild';
import fs from 'node:fs';

async function build() {
    await esbuild.build({
        entryPoints: ['src/BacklogWidget.tsx'],
        bundle: true,
        outfile: 'dist/widget.js',
        format: 'esm',
        minify: true,
        platform: 'browser',
        target: ['es2020'],
        jsx: 'automatic',
    });

    // Create CSS (simple for now)
    if (!fs.existsSync('dist')) {
        fs.mkdirSync('dist');
    }
    fs.writeFileSync('dist/widget.css', `
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 16px; }
        .carousel { display: flex; gap: 16px; overflow-x: auto; padding-bottom: 16px; }
        .card { min-width: 250px; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .card h3 { margin: 0 0 8px 0; font-size: 16px; }
        .status { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .status.todo { background: #fee2e2; color: #991b1b; }
        .status.doing { background: #fef3c7; color: #92400e; }
        .status.done { background: #dcfce7; color: #166534; }
    `);
}

build().catch(console.error);
