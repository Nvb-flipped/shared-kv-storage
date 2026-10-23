"""Create grayscale/color-vision review sheets from actual exported figures."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from colorspacious import cspace_convert
from tools.author_metadata import png_properties


def sheet(files, name, columns, thumb, modes):
    out = ROOT/'results/qa'; out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('DejaVuSans.ttf', 18)
    for mode in modes:
        width, height = thumb
        canvas = Image.new('RGB', (columns*width, 40+((len(files)+columns-1)//columns)*(height+30)), 'white')
        draw = ImageDraw.Draw(canvas); draw.text((10, 8), f'{name}: {mode}; review aid, not accessibility certification', fill='black', font=font)
        for i, file in enumerate(files):
            im = Image.open(file).convert('RGB'); im.thumbnail((width-12, height-8))
            if mode == 'grayscale': im = im.convert('L').convert('RGB')
            elif mode != 'original':
                data = cspace_convert(np.array(im)/255, {'name': 'sRGB1+CVD', 'cvd_type': mode, 'severity': 100}, 'sRGB1')
                im = Image.fromarray((np.clip(data, 0, 1)*255).astype('uint8'))
            x, y = i%columns*width, 40+i//columns*(height+30)
            canvas.paste(im, (x+6, y)); draw.text((x+8, y+height), file.stem, fill='black', font=font)
        canvas.save(out/f'{name}-{mode}.png', dpi=(150, 150), **png_properties())


def main():
    manifest = json.loads((ROOT/'results/framework/figure-manifest.json').read_text())
    figures = [ROOT/p for p in manifest['outputs'] if p.endswith('.png')]
    modes = ('original', 'grayscale', 'protanomaly', 'deuteranomaly', 'tritanomaly')
    sheet(figures, 'figures', 2, (700, 420), modes)
    (ROOT/'results/framework/visual-audit.json').write_text(json.dumps({'author': 'Paco', 'figures': len(figures),
        'modes': modes, 'redundant_encodings': ['node letters', 'markers', 'hatches', 'numeric labels', 'counts and shares'],
        'manual_review': 'Pending inspection; simulations alone do not certify accessibility.'}, indent=2)+'\n')
    print('Saved review sheets from actual exported artifacts.')


if __name__ == '__main__': main()
