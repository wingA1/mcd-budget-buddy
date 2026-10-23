"""Create a self-contained installable skill zip without private files."""
from pathlib import Path
import argparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def build(destination):
    sources = [(ROOT / 'skills/mcd-budget-buddy/SKILL.md', 'mcd-budget-buddy/SKILL.md')]
    sources += [(p, 'mcd-budget-buddy/scripts/' + p.name) for p in (ROOT / 'scripts').glob('*.py')
                if p.name != 'package_skill.py']
    sources += [(p, 'mcd-budget-buddy/examples/' + p.name) for p in (ROOT / 'examples').glob('*.json')]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stable ordering and timestamps make the same source build reproducibly.
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in sorted(sources, key=lambda pair: pair[1]):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/mcd-budget-buddy-skill.zip')
    args = parser.parse_args()
    print(build(args.output))

if __name__ == '__main__': main()
