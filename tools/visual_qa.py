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
    from PIL import Image, ImageDraw, ImageFont
    manifest = read_json(args.input/'figure-manifest.json')
    require(digest(args.input/'summary.json') == manifest['summary_sha256'], 'Figure summary hash differs.')
    files = []
    for name, expected in manifest['outputs'].items():
        path = args.input/name
        require(digest(path) == expected, f'Figure hash differs: {name}')
        if path.suffix == '.png':
            files.append(path)
    width, height = 720, 450
    sheet = Image.new('RGB', (width*2, ((len(files)+1)//2)*(height+28)), 'white')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)
    for i, path in enumerate(files):
        with Image.open(path) as source:
            image = source.convert('RGB')
        image.thumbnail((width-12, height-8))
        x, y = i%2*width, i//2*(height+28)
        sheet.paste(image, (x+6, y))
        draw.text((x+8, y+height), path.stem, fill='black', font=font)
    sheet.save(args.input/'figure-review.png')
    sheet.convert('L').save(args.input/'figure-review-grayscale.png')
    write_json(args.input/'visual-review.json', {'png_figures': len(files),
        'hashes': 'verified', 'manual_review': 'pending',
        'scope': 'Original and grayscale review aids; not accessibility certification.'})
    print('Saved original and grayscale contact sheets; inspect them visually.')


if __name__ == '__main__':
    main()
