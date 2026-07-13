import fs from 'fs';
import path from 'path';

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (let entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else if (entry.isFile() && entry.name.endsWith('.json')) {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

try {
  copyDir('src/data', 'dist/data');
  console.log('Successfully copied src/data to dist/data');
} catch (err) {
  console.error('Error copying data:', err);
  process.exit(1);
}
