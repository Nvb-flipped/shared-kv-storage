"""Make a contact sheet of a current run's actual PNG exports."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharedkv.analysis import read_json, require
from sharedkv.study import digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
        import numpy as np
        from colorspacious import cspace_convert
    except ImportError as exc:
        parser.exit(1, 'Install requirements-dev.txt for complete grayscale and color-vision review sheets.\n')
    manifest = read_json(args.input/'figure-manifest.json')
    require(digest(args.input/'summary.json') == manifest['summary_sha256'], 'Figure summary hash differs.')
    files = []
    for name, expected in manifest['outputs'].items():
        path = args.input/name
        require(digest(path) == expected, f'Figure hash differs: {name}')
        if path.suffix == '.png':
            files.append(path)
    width, height = 720, 450
    font = ImageFont.load_default(size=16)
    modes = ('original', 'grayscale', 'protanomaly', 'deuteranomaly', 'tritanomaly')
    sheets = {}
    for mode in modes:
        sheet = Image.new('RGB', (width*2, ((len(files)+1)//2)*(height+28)), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, path in enumerate(files):
            with Image.open(path) as source:
                image = source.convert('RGB')
            image.thumbnail((width-12, height-8))
            if mode == 'grayscale':
                image = image.convert('L').convert('RGB')
            elif mode != 'original':
                values = cspace_convert(np.asarray(image)/255,
                    {'name': 'sRGB1+CVD', 'cvd_type': mode, 'severity': 100}, 'sRGB1')
                image = Image.fromarray((np.clip(values, 0, 1)*255).astype('uint8'))
            x, y = i%2*width, i//2*(height+28)
            sheet.paste(image, (x+6, y))
            draw.text((x+8, y+height), path.stem, fill='black', font=font)
        name = 'figure-review.png' if mode == 'original' else f'figure-review-{mode}.png'
        info = PngImagePlugin.PngInfo(); info.add_text('Author', 'Paco')
        exif = Image.Exif(); exif[315] = 'Paco'; exif[40093] = 'Paco\0'.encode('utf-16le')
        sheet.save(args.input/name, pnginfo=info, exif=exif.tobytes())
        sheets[mode] = {'file': name, 'sha256': digest(args.input/name)}
    write_json(args.input/'visual-review.json', {'png_figures': len(files),
        'hashes': 'verified', 'manual_review': 'pending', 'sheets': sheets,
        'scope': 'Original, grayscale and three color-vision simulations. Review aids, not accessibility certification.'})
    print('Saved original, grayscale and three color-vision review sheets; inspect them visually.')


if __name__ == '__main__':
    main()
